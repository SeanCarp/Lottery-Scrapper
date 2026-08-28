import pickle
import re
import time, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


LINK = "https://www.wvlottery.com/games/scratch-offs"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PROXY_INTERVAL_SECONDS = 3.0
PROXY_RETRIES = 5
CACHE_DIRECTORY = Path(__file__).with_name("Gary_log") / "Scraped_Data"
date = datetime.now().strftime("%m-%d")
LINKS_PICKLE = CACHE_DIRECTORY / f"{date}_wv_links.pkl"
TICKET_DATA_PICKLE = CACHE_DIRECTORY / f"{date}_wv_ticket_data.pkl"
_last_proxy_request = 0.0


def load_pickle(pickle_file, function, *args):
    """Load today's cached value, or create and cache it."""
    if pickle_file.exists():
        print(f"'{pickle_file}' file found. Loading data...")
        with pickle_file.open("rb") as file:
            return pickle.load(file)

    print(f"'{pickle_file}' file NOT found. Creating new...")
    data = function(*args)
    pickle_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = pickle_file.with_suffix(".tmp")
    with temporary.open("wb") as file:
        pickle.dump(data, file)
    temporary.replace(pickle_file)
    return data


def _translation_proxy_url(link):
    parsed = urlsplit(link)
    if parsed.hostname is None or parsed.hostname.endswith("translate.goog"):
        return link
    proxy_host = parsed.hostname.replace(".", "-") + ".translate.goog"
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(
        [("_x_tr_sl", "auto"), ("_x_tr_tl", "en"), ("_x_tr_hl", "en")]
    )
    return urlunsplit((parsed.scheme, proxy_host, parsed.path, urlencode(query), parsed.fragment))


def _open_proxy_page(link, headers):
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


def _open_page(link):
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


def emulate_webbrowser(link):
    """Fetch the server-rendered page, using a proxy if needed."""
    with _open_page(link) as response:
        soup = BeautifulSoup(response.read(), "html.parser")
    print(f"Successful webpage scrape {link}\n")
    return soup


def _next_scratch_offs(soup):
    """Extract scratch-off records embedded in the Next.js flight response."""
    prefix = "self.__next_f.push("
    chunks = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if not text.startswith(prefix):
            continue
        try:
            arguments = json.loads(text[len(prefix) : text.rfind(")")])
        except (json.JSONDecodeError, ValueError):
            continue
        if len(arguments) >= 2 and arguments[0] == 1 and isinstance(arguments[1], str):
            chunks.append(arguments[1])

    payload = "".join(chunks)
    marker = '"scratchOffs":'
    position = payload.find(marker)
    if position == -1:
        raise ValueError("Scratch-off data was not found in the page")
    records, _ = json.JSONDecoder().raw_decode(payload[position + len(marker) :])
    return records


def _parse_date(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _is_active(game, now=None):
    now = now or datetime.now(timezone.utc)
    return _parse_date(game["startDate"]) <= now < _parse_date(game["endDate"])


def scrape_main(link):
    """Return active ticket titles and detail-page links."""
    games = _next_scratch_offs(emulate_webbrowser(link))
    base = link.rstrip("/") + "/"
    return [
        [game["title"], urljoin(base, game["slug"])]
        for game in games
        if _is_active(game)
    ]


def _number(value):
    matches = re.findall(r"\d+(?:\.\d+)?", str(value))
    if not matches:
        raise ValueError(f"No number found in {value!r}")
    return float(matches[-1])


def scrape_ticket(ticket):
    """Return one ticket using the dictionary shape consumed by existing logic."""
    title, link = ticket

    records = _next_scratch_offs(emulate_webbrowser(link))
    if not records:
        raise ValueError(f"Ticket data was not found for {title}")
    game = records[0]
    prize_details = game.get("prizeDetails") or []
    required = (game.get("odds"), game.get("totalTickets"), game.get("ticketPrice"))
    if not prize_details or any(value is None for value in required):
        return None

    result = {
        "Title": title,
        "Odds": _number(game["odds"]),
        "Total": int(game["totalTickets"]),
        "Remaining": sum(int(prize["remainingPrizes"]) for prize in prize_details),
        "Price": f"${game['ticketPrice']}",
    }
    print(title, "completed")
    return result


def scrape_tickets(tickets):
    return list(filter(None, (scrape_ticket(ticket) for ticket in tickets)))


def calc_and_sort_data(ticket_data):
    for item in ticket_data:
        odds = item["Odds"]
        total = item["Total"]
        remaining = item["Remaining"]
        if remaining == 0:
            item["Percentage"] = float("-inf")
            continue

        total_remaining_ratio = total / remaining
        half = total_remaining_ratio / 2.0
        difference = total_remaining_ratio - odds
        item["Percentage"] = round(
            half
            - (0.5 * difference * (1.0 - (odds * remaining) / total) / half),
            2,
        )
    return sorted(ticket_data, key=lambda data: data["Percentage"])


def main():
    tickets = load_pickle(LINKS_PICKLE, scrape_main, LINK)
    ticket_data = load_pickle(TICKET_DATA_PICKLE, scrape_tickets, tickets)
    ticket_data = calc_and_sort_data(ticket_data)

    if ticket_data:
        output = "\n".join(str(ticket) for ticket in ticket_data[-9:])
        print(output)
        return output
    return "There are no good tickets"



if __name__ == "__main__":
    main()