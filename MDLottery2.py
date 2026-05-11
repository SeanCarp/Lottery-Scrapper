import urllib.request as urllib2
from bs4 import BeautifulSoup
import Pushover
import os

LINK = 'https://www.mdlottery.com/news/top-40-scratch-offs/'

def emulate_webbrowser(LINK):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    response = opener.open(LINK)
    return BeautifulSoup(response, 'html.parser') # Loads up the main URL

def scrape_main(LINK):
    soup = emulate_webbrowser(LINK)
    table_row = soup.tbody.find_all("tr")

    tickets = []
    for item in table_row: # Loops through all 40 tickets
        a_tag, percentage = item.find_all("td")[1:3]

        title = a_tag.a.text
        href = a_tag.a.get("href")
        percentage = float(percentage.text[:-1])
        tickets.append([title, href, percentage])
    return tickets

def scrape_ticketPage(TICKET):
    title, href, percentage = TICKET
    bold_data = '' # Initializes unordered list outside of loops
    for i in range(100): # This is a loop to "refresh" the request
        while True:
            try:
                soup = emulate_webbrowser(href)
                ul = soup.find("ul","primary")
                bold_data = ul.find_all("strong") 
                break
            except Exception as e:
                print('FAILED:',title,'\n')
                return   
        break
           
    price = bold_data[0].text
    odds = float(bold_data[-2].span.text)

    td = soup.tbody.find_all("td")
    starting = [int(i.text) for i in td[1::3]]
    remainder = [int(i.text) for i in td[2::3]]

    top_prize = td[2].text + "/" + td[1].text
    created = int(sum(starting)*odds)
    outstanding = int(created*(1.0-(percentage/100.0)))
    new_odds = round((outstanding/sum(remainder)), 2)

    print(title, odds, new_odds)

    if(odds >= new_odds):
        return (dict([('Title', title),
                    ('Price', price),
                    ('Percentage', percentage),
                    ('Top Prize', top_prize),
                    ('Odds', odds),
                    ('New Odds', new_odds)]))
    return

def main():
    tickets = scrape_main(LINK)
    better_tickets = list(filter(None,[scrape_ticketPage(i) for i in tickets]))

    if len(better_tickets) != 0:
        return "\n".join(str(x) for x in better_tickets)
    return "There are no better tickets"

#RUN THE FUNCTIONS
if __name__ == '__main__':
    better_tickets = main()
    liberator = Pushover(os.environ['PUSHOVER_USERKEY'], os.environ['PUSHOVER_TOKEN'])
    liberator.send_notification(better_tickets, 'MDLottery')    