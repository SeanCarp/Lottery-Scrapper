import sys, os, time, pickle
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Result import Result

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

# Side note before I get to distracted
""" When reconfiguring the Gmail.py make sure to have no While loops.
While loops go in the main script and that is also where the new threads are returned.
To make the split between parser_command add an intent pipeline to NLP. And
add the library that the command will use in the training data. A transformer may work
but it feels like to big of a cop out and may not be what I truly want.

Also, for future notes I need to make it so that the NLP has better response back to the user.
I think this where transformers really pull ahead."""

TOP_40_LINK = 'https://www.mdlottery.com/news/top-40-scratch-offs/'
SCRATCH_LINK = 'https://www.mdlottery.com/games/scratch-offs/'

date = datetime.now().strftime('%m-%d')
LINKS_PICKLE = f"Gary_log/Scraped_Data/{date}_40_links.pkl"
TICKET_DATA_PICKLE = f"Gary_log/Scraped_Data/{date}_ticket_data.pkl"

def load_pickle(PICKLE_FILE:str, function, *args):
    """ Loads pickle if it exists, otherwise runs function
    Args:
        PICKLE_FILE (str) - File to check if it currently exists"""
    if os.path.exists(PICKLE_FILE):
        print(f"'{PICKLE_FILE}' file found. Loading data...")
        with open(PICKLE_FILE, "rb") as f:
            data = pickle.load(f)
    else:
        print(f"'{PICKLE_FILE}' file NOT found. Creating new...")
        data = function(*args)
        with open(PICKLE_FILE, "wb") as f:
            pickle.dump(data, f)
    return data

def emulate_webbrowser(LINK:str, headless:bool=True) -> webdriver.Edge:
    # TODO: Switch this to return driver
    """ 
    Emulates webbrowser in Mozilla and loads given website.
    Args:
        LINK (str): The URL of the website page to be scraped.
    Returns:
        webdriver object of given link.
    """
    options = Options()
    options.add_argument('--window-size=1920,1080')
    # Full screen mode
    options.add_argument('--headless') if headless else None

    driver = webdriver.Edge(options=options)
    driver.get(LINK)
    time.sleep(3)       # Give it time to load

    print(f'Successful webpage scrape {LINK}\n')
    return driver

def scrape_top_40(LINK:str) -> list[str, str]:
    """
    Scrapes the 40 selling tickets game name and percentage sold
    """
    driver = emulate_webbrowser(LINK)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    table_row = soup.tbody.find_all("tr")

    tickets = []
    for item in table_row: # Loops through all 40 tickets
        # Example: ['\n', num, '\n', game_num, '\n', game_name, '\n', %_sold, ...]
        game_num = item.contents[3].text
        title = item.contents[5].text
        percentage = item.contents[7].text
        tickets.append([game_num, title, percentage])
    print(len(tickets), "tickets found.")
    return tickets

def scrape_scratch(LINK:str, tickets:list) -> list:
    """ Scrapes the ticket card website for the tickets listed
    Args:
        LINK (str) - Hyperlink to website
        tickets (str) - [ticket_num, title, % sold]
        
    Returns:
        list - [tickets[i], price, top_prize, odds, (remaining, total)]
    """
    driver = emulate_webbrowser(LINK)

    buttons = []
    ticket_data_list = []
    for idx, ticket in enumerate(tickets):
        num, title, _ = ticket
        print(title)

        # Card logic for top_prize, price, odds
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        redefined = soup.select(f'li[id="ticket_{num}"]')[0]
        
        top_prize = redefined.select('strong[class="topprize"]')[0].text
        price = redefined.select('div[class="price"]')[0].text[1:] # Gets rid of '$'
        odds = redefined.select('span[class="probability"]')[0].text

        print(top_prize, price, odds)

        # Button logic for starting and remainder
        button = driver.find_element(By.CSS_SELECTOR, f'[href="#prize_details_{num}"]')
        buttons.append(button)

        """ StackOverflow: Pass in true to scrollIntoView if the object 
        you're scrolling to is beneath where you currently are, false 
        if the object you're scrolling to is above where you currently 
        are. I had a hard time figuring that out."""
        if idx != 0 and button.location['y'] < buttons[idx-1].location['y']:
            flag = "false" # Javascript bool
        else:
            flag = "true"   # Javascript bool
        driver.execute_script(f"arguments[0].scrollIntoView({flag});", button)

        time.sleep(2)   # Let damn website load
        button.click()        

        # BeautifulSoup scrape for Remaining and Total
        ticket_card = BeautifulSoup(driver.page_source, 'html.parser')
        ticket_data = ticket_card.tbody.find_all("td")
        total = sum([int(item.text) for item in ticket_data[1::3]])
        remaining = sum([int(item.text) for item in ticket_data[2::3]])
        print("Remaining:", remaining)
        print("Total:", total,"\n")
        ticket_data_list.append([tickets[idx], price, top_prize, odds, (remaining, total)])

        # Close btn
        driver.find_element(By.CLASS_NAME, "mfp-close").click()

    print(len(buttons), "buttons found.\n")
    driver.close()
    return ticket_data_list


def recalculate_odds(ticket_data:list, threshold:float=1.015) -> list:
    """
    Args:
        ticket_data (list) - [tickets[i], price, top_prize, odds, (remaining, total)]
    Returns:
        list - [title, price, top_prize, odds, new_odds, Percentage]
    """
    better_odds = []
    for item in ticket_data:
        ticket_num, title, percentage = item[0]
        price = float(item[1])
        top_prize = item[2]
        odds = float(item[3])
        remaining, total_win = map(int, item[4])

        percentage = float(percentage[:-1])
        created = int(total_win*odds)
        outstanding = int(created*(1.0-(percentage/100.0)))

        if remaining == 0:
            print(f"Skipping {title} (No remaining tickets)")
            continue

        new_odds = round((outstanding/remaining),2)
        percentage = str(percentage) + "%"

        # Only care if there are better odds or less than 1%
        if new_odds < (odds * threshold):
            print(title, price, top_prize)
            print(new_odds, odds, percentage, "\n")
            better_odds.append([title, price, top_prize, new_odds, odds, percentage])
    return better_odds

def pretty_print(data:list[list]) -> None:
    """ Cleans up the print statement for the notification """
    """ Data: [list[list]] = [[title, price, top_prize, new_odds, odds, percentage]]"""
    output = ""
    for ticket in data:
        try:
            title, price, top_prize, new_odds, odds, percentage = ticket
            output += f"{title}, Price: ${price}, Top Prize: {top_prize}\n\
                Odds: {odds}, New Odds: {new_odds}, {percentage}\n\n"
        except Exception as e:
            return e
    return output

def main() -> 'Result':
    try:
        tickets = load_pickle(LINKS_PICKLE, scrape_top_40, TOP_40_LINK)
        ticket_data = load_pickle(TICKET_DATA_PICKLE, scrape_scratch, SCRATCH_LINK, tickets)
        data = recalculate_odds(ticket_data)
        return Result(True, pretty_print(data))
    
    except Exception as e:
        return Result(False, f"Error scraping MDLottery: {e}")
    


if __name__ == '__main__':
    chk_1 = time.perf_counter()
    tickets = load_pickle(LINKS_PICKLE, scrape_top_40, TOP_40_LINK)
    
    chk_2 = time.perf_counter()
    ticket_data = load_pickle(TICKET_DATA_PICKLE, scrape_scratch, SCRATCH_LINK, tickets)
    chk_3 = time.perf_counter()
    
    test = recalculate_odds(ticket_data)
    chk_4 = time.perf_counter()

    print(f"Function 1: {chk_2 - chk_1:.6f} seconds")
    print(f"Function 2: {chk_3 - chk_2:.6f} seconds")
    print(f"Function 3: {chk_4 - chk_3:.6f} seconds")