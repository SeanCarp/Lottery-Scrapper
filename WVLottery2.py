import urllib.request as urllib2
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

LINK = 'https://www.wvlottery.com/games/scratch-offs'

#Loads the website by emulation [Requirement of WVLottery]
def emulate_webbrowser(LINK):

    #This allows chrome to load while being headless
    options = Options() #Webpage is open for ~3secs
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--headless')

    #Loads the url
    driver = webdriver.Chrome(options=options)
    driver.get(LINK)
    
    html = driver.page_source
    print(f'Successful webpage scrape {LINK}')
    print()
    driver.quit() #Closes the webpage

    return BeautifulSoup(html, 'html.parser')

#Scrapes the main page & returns list of (tiles, links)
def scrape_main(LINK):
    soup = emulate_webbrowser(LINK)
    main = soup.main
    


    div = soup.main.article.find(id="results").find_all('div')
    tickets = []
    for i in div:
        if(i['data-status'] == 'status-new' or i['data-status'] == 'status-current'):
            tickets.append(i.a)

    links = [item.get('href') for item in tickets]
    titles = [item.find(class_='title').text for item in tickets]
    return [list(i) for i in zip(titles, links)]

#Scrapes a ticket page
#Data to collect: Ticket Price, Odds, Remaining_Tickets, Total_Tickets
def scrape_ticket(ticket):
    title, link = ticket
    soup = emulate_webbrowser(link)
    div = soup.article.div
    pic, right_table, btm_table = div.contents[1::2]
    
    #Right Table
    right_rows = right_table.find_all('tr')
    price = right_rows[0].contents[3].text
    odds = float(right_rows[2].contents[3].text[2:])
    total_tickets = int(right_rows[3].contents[3].text.replace(",",''))

    #Bottom Table
    bottom_rows = btm_table.find_all('tr')
    data = bottom_rows[1:]
    data = [item.find_all('td') for item in data]

    debug = [int(item[3].text.replace(",","")) for item in data]
    remaining = sum([int(item[3].text.replace(",","")) for item in data])

    print(title, 'completed')
    return {'Title': title,
            'Odds': odds,
            'Total': total_tickets,
            'Remaining': remaining,
            'Price': price}

def calc_and_sort_data(ticket_data):
    for item in ticket_data:
        o = item['Odds']
        t = item['Total']
        r = item['Remaining']

        TR = t/r
        half = TR/2.0
        sub = TR - o

        percentage = round(half - (.5* sub* (1.0-(o*r)/t)/half), 2)
        item["Percentage"] = percentage
    return sorted(ticket_data, key=lambda d: d['Percentage'])
    

def main(): #Completed email address
    tickets = scrape_main(LINK)
    ticket_data = list(filter(None, [scrape_ticket(item) for item in tickets]))
    ticket_data = calc_and_sort_data(ticket_data)

    print("\n".join(str(x) for x in ticket_data[-9:]))
    if len(ticket_data) != 0:
        return "\n".join(str(x) for x in ticket_data[-9:])
    
    return "There are no good tickets"

#RUN THE FUNCTIONS
if __name__ == '__main__':
    tickets = scrape_main(LINK)
    ticket_data = list(filter(None,[scrape_ticket(item) for item in tickets]))
    ticket_data = calc_and_sort_data(ticket_data)
    print("\n".join(str(x) for x in ticket_data[-9:]))