from selenium import webdriver
from selenium.webdriver.chrome.options import Options

LINK = 'https://www.wvlottery.com/games/scratch-offs'

# Loads the website by emulation
def emulate_webbrowser(link):
    # This allows chrome to load while being headless
    options = Options()
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--headless')

    # Loads the url
    driver = webdriver.Chrome(options=options)
    driver.get(link)

    html = driver.page_source
    