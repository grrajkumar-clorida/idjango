# utils/pe_scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

def fetch_nifty_pe():
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)

    driver.get("https://www.screener.in/company/NIFTY/") #https://www.niftyindices.com/reports/historical-data
    time.sleep(5)  # Wait for JS to load

    soup = BeautifulSoup(driver.page_source, "html.parser")
    pe_value = 0
    # Update this selector based on the actual page
    for li in soup.select("ul#top-ratios li"):
        label = li.find("span", class_="name")
        value = li.find("span", class_="number")
        if label and "P/E" in label.text:
            pe_value = float(value.text.strip())

    
    driver.quit()

    return pe_value

'''
from datetime import date, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def fetch_nifty_pe():
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)
    driver.get("https://www.niftyindices.com/reports/historical-data")

    wait = WebDriverWait(driver, 20)

    try:
        # Step 1: Click the dropdown
        historical_menu = wait.until(EC.element_to_be_clickable((By.ID, "HistoricalMenu")))
        historical_menu.click()

        # Step 1.5: Wait and select "P/E, P/B & Div.Yield values" (li.form4)
        form4_option = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "li.form4")))
        form4_option.click()

        # Step 2: Select 'Equity' in type dropdown
        wait.until(EC.element_to_be_clickable((By.ID, "ddlHistoricaldivtypee"))).click()
        driver.find_element(By.CSS_SELECTOR, "select#ddlHistoricaldivtypee option[value='Equity']").click()

        time.sleep(5)  # wait for index dropdown to load

        # Step 3: Select 'NIFTY 50'
        driver.find_element(By.CSS_SELECTOR, "select#ddlHistoricaldivtypeeindex option[value='NIFTY 50']").click()


        # # Step 1: Open page
        # driver.get("https://www.niftyindices.com/reports/historical-data")
        # time.sleep(3)

        # # Step 1.1: Click the 'HistoricalMenu' dropdown and select 'Form 4'
        # driver.find_element(By.ID, "HistoricalMenu").click()
        # time.sleep(1)
        # form4_option = driver.find_element(By.LINK_TEXT, "P/E, P/B & Div.Yield values")
        # form4_option.click()
        # time.sleep(3)

        # # Step 2: Select 'Equity' from dropdown with id='ddlHistoricaldivtypee'
        # div_type_dropdown = Select(driver.find_element(By.ID, "ddlHistoricaldivtypee"))
        # div_type_dropdown.select_by_value("Equity")
        # time.sleep(10)

        # # Step 3: Select 'NIFTY 50' from index dropdown
        # index_dropdown = Select(driver.find_element(By.ID, "ddlHistoricaldivtypeeindex"))
        # index_dropdown.select_by_value("NIFTY 50")
        # time.sleep(3)

        # Step 4: Pick yesterday's date
        yesterday = (date.today() - timedelta(days=1)).strftime("%d-%m-%Y")
        datepicker = driver.find_element(By.ID, "datepickerFromDivYield")
        datepicker.clear()
        datepicker.send_keys(yesterday)
        time.sleep(2)

        # Step 5: Click submit
        driver.find_element(By.ID, "submit_buttonDivdata").click()
        time.sleep(5)  # Allow time for data to load

        # Step 6: Scrape the PE value
        soup = BeautifulSoup(driver.page_source, "html.parser")
        pe_cell = soup.find("td", class_="thpe")
        if pe_cell:
            try:
                pe_value = float(pe_cell.text.strip())
            except ValueError:
                pe_value = None
        else:
            pe_value = None


    finally:
        driver.quit()

# input id=HistoricalMenu click and dropdown need to select "form4"
# step 2: 
# dropdown id = ddlHistoricaldivtypee select option value="Equity"
# wait for 10 sec 
# step 3: 
# select dropdown id=ddlHistoricaldivtypeeindex option value="NIFTY 50"
# step4:
# click datapicker id="datepickerFromDivYield" and set yesteday date.
# step5:
# click submit button id="submit_buttonDivdata" 
# step 6:
'''