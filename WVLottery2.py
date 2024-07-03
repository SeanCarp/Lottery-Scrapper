import urllib.request as urllib2
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText

LINK = 'https://www.wvlottery.com/scratch-offs'

#Loads the website by emulation [Requirement of WVLottery]
def emulate_webbrowser(LINK):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    response = opener.open(LINK)
    return BeautifulSoup(response, 'html.parser') # Loads up the main URL

#Scrapes the main page & returns list of (tiles, links)
def scrape_main(LINK):
    soup = emulate_webbrowser(LINK)
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


#This is the same function as the one in MDLottery
def text_message(subject, body, *to):
    text = f'\n{body["Title"]}\nPrice: {body["Price"]}    Odds: {body["Odds"]}\nChance of being (+): {body["Percentage"]}'
    msg = MIMEText(text) #Not sure what this does but, I know it works

    if(len(to) == 2):
        mobile_providers = {'at&t': '@mms.att.net',
                        'cricket wireless': '@mms.att.net',
                        'metro pcs': '@metropcs.sms.us',
                        'tmobile': '@tmomail.net',
                        'us cellular': '@email.uscc.net',
                        'verizon': '@vtext.com'}
        msg['to'] = to[0] + mobile_providers.get(to[1])
    else:
        msg['to'] = to[0]
    
    msg['subject'] = subject
    msg['from'] = "swcarpenter04@gmail.com"
    password = "hwreortjnqwtjqcg"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("swcarpenter04@gmail.com", password)
    server.send_message(msg)
    print('Sent')
    

def main(phone_number): #Completed email address
    tickets = scrape_main(LINK)
    ticket_data = list(filter(None, [scrape_ticket(item) for item in tickets]))
    ticket_data = calc_and_sort_data(ticket_data)
    [text_message('WV Lottery', x, phone_number) for x in ticket_data[-4:]]

#RUN THE FUNCTIONS
if __name__ == '__main__':
    print("WARNING: All text messages will come from swcarpenter04@gmail.com")
    mobile_provider = input("Enter mobile provider (AT&T, Cricket Wireless, Metro PCS, Tmobile, US Cellular, Verizon)\n").lower()
    phone_number = input("Please enter phone number (raw digits)\n")
    
    tickets = scrape_main(LINK)
    ticket_data = list(filter(None,[scrape_ticket(item) for item in tickets]))
    ticket_data = calc_and_sort_data(ticket_data)
    [text_message('WV Lottery', x, phone_number, mobile_provider) for x in ticket_data[-4:]]