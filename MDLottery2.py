import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
import smtplib

LINK = 'https://www.mdlottery.com/news/top-40-scratch-offs/'

def scrape_main(LINK):
    main_url = requests.get(LINK).content
    soup = BeautifulSoup(main_url, 'html.parser') # Loads up the main URL
    print(soup)
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
                url = requests.get(href, timeout=1).content # This can break if page didn't load
                soup = BeautifulSoup(url, 'html.parser').body # Loads up the ticket's URL
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

    print(title)
    if(odds >= new_odds):
        return (dict([('Title', title),
                    ('Price', price),
                    ('Percentage', percentage),
                    ('Top Prize', top_prize),
                    ('Odds', odds),
                    ('New Odds', new_odds)]))
    return

#This is the same function as the one in MDLottery
def text_message(subject, body, *to):
    text = f'\n{body["Title"]}\nPrice: {body["Price"]}\nPercentage: {body["Percentage"]}\nOdds: {body["Odds"]}\nNew Odds: {body["New Odds"]}\nTop Prizes: {body["Top Prize"]}'
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
    password = "qcczprggcwopltpy"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("swcarpenter04@gmail.com", password)
    server.send_message(msg)
    print('Sent')

def main(phone_number):
    tickets = scrape_main(LINK)
    better_tickets = list(filter(None,[scrape_ticketPage(i) for i in tickets]))
    [text_message('MD Lottery', x, phone_number) for x in better_tickets]

#RUN THE FUNCTIONS
if __name__ == '__main__':
    print("WARNING: All text messages will come from swcarpenter04@gmail.com")
    mobile_provider = input("Enter mobile provider (AT&T, Cricket Wireless, Metro PCS, Tmobile, US Cellular, Verizon)\n").lower()
    phone_number = input("Please enter phone number (raw digits)\n")
    
    tickets = scrape_main(LINK)
    better_tickets = list(filter(None,[scrape_ticketPage(i) for i in tickets]))
    [text_message('MD Lottery', x, phone_number, mobile_provider) for x in better_tickets]    