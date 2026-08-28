import os
import pickle
import re
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


TOP_40_LINK = "https://www.mdlottery.com/top-40-scratch-off/"
SCRATCH_LINK = "https://www.mdlottery.com/games/scratch-offs/"

date = datetime.now().strftime("%m-%d")
LINKS_PICKLE = f"Gary_log/Scraped_Data/{date}_md_40_links.pkl"
TICKET_DATA_PICKLE = f"Gary_log/Scraped_Data/{date}_md_ticket_data.pkl"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PROXY_INTERVAL_SECONDS = 3.0
PROXY_RETRIES = 5
_last_proxy_request = 0.0

def _translation_proxy_url(link: str) -> str:
    """Route a blocked lottery URL through Google's transparent web proxy."""
    parsed = urlsplit(link)
    if parsed.hostname is None or parsed.hostname.endswith("translate.goog"):
        return link
    proxy_host = parsed.hostname.replace(".", "-") + ".translate.goog"
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(
        [("_x_tr_sl", "auto"), ("_x_tr_tl", "en"), ("_x_tr_hl", "en")]
    )
    return urlunsplit((parsed.scheme, proxy_host, parsed.path, urlencode(query), parsed.fragment))


def _open_proxy_page(link: str, headers: dict[str, str]):
    global _last_proxy_request

    for attempt in range(PROXY_RETRIES):
        interval = time.monotonic() - _last_proxy_request
        if interval < PROXY_INTERVAL_SECONDS:
            time.sleep(PROXY_INTERVAL_SECONDS - interval)
        _last_proxy_request = time.monotonic()

        try:
            return urlopen(Request(link, headers=headers), timeout=30)
        except HTTPError as error:
            if error.code != 429 or attempt == PROXY_RETRIES - 1:
                raise
            retry_after = error.headers.get("Retry-After", "")
            delay = (
                float(retry_after)
                if retry_after.isdigit()
                else min(60.0, 10.0 * (2**attempt))
            )
            print(f"Proxy rate limited; retrying in {delay:g} seconds...")
            time.sleep(delay)

    raise RuntimeError("Proxy retry loop exited unexpectedly")


def _open_page(link: str):
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": USER_AGENT,
    }
    try:
        return urlopen(Request(link, headers=headers), timeout=30)
    except URLError:
        proxy_link = _translation_proxy_url(link)
        if proxy_link == link:
            raise
        return _open_proxy_page(proxy_link, headers)


def load_pickle(pickle_file: str, function, *args):
    """Load today's cached value, or create and cache it."""
    if os.path.exists(pickle_file):
        print(f"'{pickle_file}' file found. Loading data...")
        with open(pickle_file, "rb") as file:
            return pickle.load(file)

    print(f"'{pickle_file}' file NOT found. Creating new...")
    data = function(*args)
    directory = os.path.dirname(pickle_file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(pickle_file, "wb") as file:
        pickle.dump(data, file)
    return data


def emulate_webbrowser(link: str, headless: bool = True) -> BeautifulSoup:
    """Fetch an official lottery page, using a proxy if it resets the connection."""
    del headless  # Kept in the public signature for existing callers.
    with _open_page(link) as response:
        soup = BeautifulSoup(response.read(), "html.parser")
    print(f"Successful webpage scrape {link}\n")
    return soup


def _latest_top_40_table(link: str) -> BeautifulSoup:
    soup = emulate_webbrowser(link)
    if soup.select_one("table.wpDataTable, table[data-wpdatatable_id]"):
        return soup

    archive_link = soup.select_one(
        'a[href*="/top-40-scratch-off/week-ending-"]'
    )
    if archive_link is None:
        raise ValueError("The latest Top 40 ranking page was not found")
    return emulate_webbrowser(urljoin(link, archive_link["href"]))

def scrape_top_40(link: str) -> list[list[str]]:
    """Return [game number, title, percentage sold] for the current Top 40."""
    soup = _latest_top_40_table(link)
    table = soup.select_one("table.wpDataTable, table[data-wpdatatable_id]")
    if table is None:
        raise ValueError("The Top 40 table was not found")

    headers = [cell.get_text(" ", strip=True).lower() for cell in table.select("thead th")]
    try:
        number_index = next(i for i, value in enumerate(headers) if "game number" in value)
        title_index = next(i for i, value in enumerate(headers) if "game name" in value)
        sold_index = next(i for i, value in enumerate(headers) if "% sold" in value)
    except StopIteration as error:
        raise ValueError("The Top 40 table columns have changed") from error

    tickets = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) <= max(number_index, title_index, sold_index):
            continue
        tickets.append(
            [
                cells[number_index].get_text(" ", strip=True),
                cells[title_index].get_text(" ", strip=True),
                cells[sold_index].get_text(" ", strip=True),
            ]
        )

    if not tickets:
        raise ValueError("The Top 40 table contained no tickets")
    print(len(tickets), "tickets found.")
    return tickets


def _scratch_endpoint(link: str) -> str:
    if "admin-ajax.php" in link:
        return link
    parsed = urlsplit(link)
    query = urlencode(
        {
            "action": "jquery_shortcode",
            "shortcode": "scratch_offs",
            "atts": '{"null":"null"}',
        }
    )
    return urlunsplit((parsed.scheme, parsed.netloc, "/wp-admin/admin-ajax.php", query, ""))


def _integer(value: str) -> int:
    return int(re.sub(r"[^0-9-]", "", value))


def scrape_scratch(link: str, tickets: list[list[str]]) -> list[list]:
    """Add price, top prize, odds, and winning-ticket totals to each ticket."""
    soup = emulate_webbrowser(_scratch_endpoint(link))
    cards = {
        card.get("id", "").removeprefix("ticket_"): card
        for card in soup.select("li.ticket[id^='ticket_']")
    }

    ticket_data_list = []
    for ticket in tickets:
        number, title, _ = ticket
        card = cards.get(number)
        if card is None:
            raise ValueError(f"Ticket {number} ({title}) was not found on the games page")

        price_node = card.select_one(".header .price")
        top_prize_node = card.select_one("strong.topprize")
        odds_node = card.select_one("span.probability")
        prize_rows = card.select(f"#prize_details_{number} tbody tr")
        if not price_node or not top_prize_node or not odds_node or not prize_rows:
            raise ValueError(f"Ticket {number} ({title}) is missing required data")

        starting = []
        remaining = []
        for row in prize_rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                starting.append(_integer(cells[1].get_text(" ", strip=True)))
                remaining.append(_integer(cells[2].get_text(" ", strip=True)))

        price = price_node.get_text(" ", strip=True).removeprefix("$")
        top_prize = top_prize_node.get_text(" ", strip=True)
        odds = odds_node.get_text(" ", strip=True)
        print(title)
        print(top_prize, price, odds)
        print("Remaining:", sum(remaining))
        print("Total:", sum(starting), "\n")
        ticket_data_list.append(
            [ticket, price, top_prize, odds, (sum(remaining), sum(starting))]
        )

    print(len(ticket_data_list), "tickets found.\n")
    return ticket_data_list


def recalculate_odds(ticket_data: list, threshold: float = 1.015) -> list:
    """Return tickets whose estimated current odds meet the existing threshold."""
    better_odds = []
    for item in ticket_data:
        _, title, percentage = item[0]
        price = float(item[1])
        top_prize = item[2]
        odds = float(item[3])
        remaining, total_win = map(int, item[4])

        percentage_value = float(percentage.removesuffix("%"))
        created = int(total_win * odds)
        outstanding = int(created * (1.0 - (percentage_value / 100.0)))

        if remaining == 0:
            print(f"Skipping {title} (No remaining tickets)")
            continue

        new_odds = round(outstanding / remaining, 2)
        percentage = str(percentage_value) + "%"
        if new_odds < (odds * threshold):
            print(title, price, top_prize)
            print(new_odds, odds, percentage, "\n")
            better_odds.append(
                [title, price, top_prize, new_odds, odds, percentage]
            )
    return better_odds


def pretty_print(data: list[list]) -> str:
    """Keep the notification text format used by existing consumers."""
    output = ""
    for title, price, top_prize, new_odds, odds, percentage in data:
        output += (
            f"{title}, Price: ${price}, Top Prize: {top_prize}\n"
            f"                Odds: {odds}, New Odds: {new_odds}, {percentage}\n\n"
        )
    return output


def main() -> str:
    tickets = load_pickle(LINKS_PICKLE, scrape_top_40, TOP_40_LINK)
    ticket_data = load_pickle(TICKET_DATA_PICKLE, scrape_scratch, SCRATCH_LINK, tickets)
    return pretty_print(recalculate_odds(ticket_data))


def cli() -> None:
    print(main(), end="")


if __name__ == "__main__":
    cli()