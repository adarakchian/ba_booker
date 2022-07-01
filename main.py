from __future__ import annotations
import typing
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.ui import Select
import time
from dataclasses import dataclass
import pickle
import os
from dotenv import load_dotenv


def try_int(x):
    try:
        return int(x)
    except ValueError:
        return None


FARE_MAP = {
    "Economy": "Economy\n(Hand baggage only)",
    "Economy (Checked baggage)": "Economy\n(Checked baggage)"
}


@dataclass
class FlightInfo:
    cabin_name: str
    origin_time: str
    origin_place: str
    destination_time: str
    destination_place: str
    price: typing.Optional[int]
    next_button: WebElement


@dataclass
class FlightParameters:
    city_start: str
    city_end: str
    travel_dt: str
    flight_time: str

    title: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    payment_method: str
    card_number: str
    card_exp: str
    cvv: str
    address_line_1: str
    address_line_2: str
    post_code: str

    cabin = 'Economy'


class BaFlightBooker:
    driver: WebDriver

    def __init__(self):
        option = Options()
        option.add_experimental_option("excludeSwitches", ["enable-automation"])
        option.add_experimental_option('useAutomationExtension', False)
        option.add_argument('--disable-blink-features=AutomationControlled')
        option.binary_location = r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe"

        dir_path = os.getcwd()
        option.add_argument(f'user-data-dir={dir_path}/selenium')
        chrome_driver = os.path.join(dir_path, "chromedriver.exe")
        w_driver = webdriver.Chrome(options=option, executable_path=chrome_driver)
        w_driver.implicitly_wait(30)
        self.driver = w_driver

    def initialize_and_preset(self):
        driver = self.driver
        driver.get("https://www.britishairways.com/")
        if os.path.exists('cookies.pkl'):
            cookies = pickle.load(open("cookies.pkl", "rb"))
            for cookie in cookies:
                driver.add_cookie(cookie)
            driver.refresh()
            time.sleep(5)

    def find_select_fare_button(self, cabin: str) -> WebElement:
        cabin_wrapper = self.driver.find_elements(By.CLASS_NAME, "cabin-wrapper ")
        if len(cabin_wrapper) != 1:
            raise ValueError("More than 1 flight is open")
        cabin_wrapper = cabin_wrapper[0]
        target_fare = FARE_MAP.get(cabin, cabin)
        flight_cards = cabin_wrapper.find_elements(By.CLASS_NAME, "flight-card")
        button = None
        for single_card in flight_cards:
            fare_name = single_card.find_element(By.CLASS_NAME, "fare-name").text
            if fare_name == target_fare:
                button = single_card.find_element(By.CLASS_NAME, "select-button")
        if button is None:
            raise ValueError("Select fare button is not found")
        return button

    def collect_all_flights(self) -> typing.List[FlightInfo]:
        elements = self.driver.find_elements(By.TAG_NAME, "app-flight-original")
        info_list = []
        for box in elements:
            details = box.find_element(By.TAG_NAME, "div")
            detail_id = details.get_attribute("id")
            if "flight" not in detail_id:
                continue
            info = self.scrape_base_info(box)
            info_list.extend(info)
        return info_list

    def find_my_flight(self, parameters: FlightParameters):
        info_list = self.collect_all_flights()
        filtered_list = filter(
            lambda flight:
            flight.origin_place == parameters.city_start
            and flight.cabin_name == parameters.cabin
            and flight.price is not None,
            info_list
        )
        filtered_list = list(filtered_list)
        target_flight = [s for s in filtered_list if s.origin_time == parameters.flight_time]
        if len(target_flight) == 0:
            raise ValueError(f"No such flight exist. Existing times are: {[s.origin_time for s in filtered_list]}")
        elif len(target_flight) > 1:
            raise ValueError(f"Multiple flights identified: {[s.origin_time for s in filtered_list]}")
        target_flight = target_flight[0]
        return target_flight

    def fill_passenger_form(self, parameters):
        driver = self.driver
        time.sleep(2)
        title = Select(driver.find_element(By.ID, "ba-select-1"))
        title.select_by_visible_text(parameters.title)

        time.sleep(1)
        first_name = driver.find_element(By.ID, "pax0-firstName-native")
        first_name.send_keys(parameters.first_name)

        time.sleep(1)
        last_name = driver.find_element(By.ID, "pax0-lastName-native")
        last_name.send_keys(parameters.last_name)

        time.sleep(1)
        email_field = driver.find_element(By.ID, "ba-input-12")
        email_field.send_keys(parameters.email)

        time.sleep(1)
        phone_field = driver.find_element(By.ID, "ba-input-13")
        phone_field.send_keys(parameters.phone_number)

        time.sleep(2)
        continue_button = driver.find_element(By.CLASS_NAME, "pax-continue")
        continue_button.click()

    def fill_credit_card_details(self, parameters):
        driver = self.driver

        time.sleep(1)
        method_field = Select(driver.find_element(By.ID, "ba-select-7"))
        method_field.select_by_visible_text(parameters.payment_method)

        time.sleep(1)
        cc_number_field = driver.find_element(By.ID, "cc-number")
        cc_number_field.send_keys(parameters.card_number)

        time.sleep(1)
        exp_date_wrapper = driver.find_element(By.ID, "expiry-date")
        exp_date_wrapper.click()
        ActionChains(driver).send_keys(parameters.card_exp).perform()

        time.sleep(1)
        cvc_field = driver.find_element(By.ID, "cc-csc")
        cvc_field.send_keys(parameters.cvv)

        time.sleep(1)
        add1 = driver.find_element(By.ID, "address-line1")
        add1.send_keys(parameters.address_line_1)

        time.sleep(1)
        add2 = driver.find_element(By.ID, "address-line2")
        add2.send_keys(parameters.address_line_2)

        time.sleep(1)
        post_code_field = driver.find_element(By.ID, "postal-code")
        post_code_field.send_keys(parameters.post_code)

    def run_search(self, parameters: FlightParameters):
        # Open BA website and set cookies from the last session
        self.initialize_and_preset()
        driver = self.driver

        # Construct search url
        url = self.construct_url(start=parameters.city_start, end=parameters.city_end, travel_date=parameters.travel_dt)
        driver.get(url)

        # Agree to cookies
        if driver.find_element(By.ID, "ensCloseBanner").is_displayed():
            driver.find_element(By.ID, "ensCloseBanner").click()

        # Wait up until 20 secs for flights tp load
        WebDriverWait(driver, 20).until(
            lambda browser: len(browser.find_elements(By.TAG_NAME, "app-flight-original")) > 4
        )

        # If any of the flight options are folded, unfold them
        for accordion in driver.find_elements(By.TAG_NAME, "ba-accordion"):
            accordion.click()

        # Find the target flight in the search and expand
        target_flight = self.find_my_flight(parameters)
        target_flight.next_button.click()
        time.sleep(2)

        # Select the relevant fare
        select_button = self.find_select_fare_button(parameters.cabin)
        select_button.click()
        time.sleep(5)

        # Agree to the terms
        agree_button = driver.find_element(By.CLASS_NAME, "agree-button")
        agree_button.click()

        # In case we do not have cookies, we need to click to proceed as guest
        if not driver.find_element(By.ID, "pax0-firstName-native").is_displayed():
            while True:
                if driver.find_element(By.CLASS_NAME, "guest-continue-button").is_displayed():
                    break
                time.sleep(3)
            guest_button = driver.find_element(By.CLASS_NAME, "guest-continue-button")
            guest_button.click()
            time.sleep(5)

        self.fill_passenger_form(parameters)
        time.sleep(5)

        # Choose seats later
        driver.find_element(By.CLASS_NAME, "choose-later-section").find_element(By.TAG_NAME, "ba-button").click()
        time.sleep(10)
        self.fill_credit_card_details(parameters)

        # Pickle cookies for future sessions
        pickle.dump(driver.get_cookies(), open("cookies.pkl", "wb"))
        print("Please press agree and pay!")

    @classmethod
    def scrape_base_info(cls, flight_box: WebElement) -> typing.List[FlightInfo]:
        basic_info = flight_box.find_element(By.CLASS_NAME, "flight-info-wrapper")
        info_line = basic_info.find_elements(By.TAG_NAME, "span")
        origin_time, origin_place = info_line[0].text.split(" ")
        destination_time, destination_place = info_line[2].text.split(" ")

        price_buttons = flight_box.find_elements(By.TAG_NAME, "button")
        infos = []
        for button in price_buttons:
            cabin_name = button.find_element(By.CLASS_NAME, "cabin-name").text
            cabin_price = button.find_element(By.CLASS_NAME, "cabin-price").text
            price = cabin_price.replace("£", "")
            int_price = try_int(price)
            flight_info = FlightInfo(
                cabin_name=cabin_name, origin_time=origin_time, destination_time=destination_time,
                origin_place=origin_place,
                destination_place=destination_place, price=int_price, next_button=button
            )
            infos.append(flight_info)

        return infos

    @staticmethod
    def construct_url(start, end, travel_date):
        url = f"https://www.britishairways.com/travel/book/public/en_gb/" \
              f"flightList?onds={start}-{end}_{travel_date}&ad=1&yad=0&ch=0&inf=0&cabin=M&flex=LOWEST"
        return url


if __name__ == '__main__':
    load_dotenv()
    params = FlightParameters(
        city_start="LCY", city_end="AMS", travel_dt="2022-07-07", flight_time="18:55",

        title=os.getenv("title"),
        first_name=os.getenv("first_name"),
        last_name=os.getenv("last_name"),
        email=os.getenv("email"),
        phone_number=os.getenv("phone_number"),
        payment_method=os.getenv("payment_method"),
        card_number=os.getenv("card_number"),
        card_exp=os.getenv("card_exp"),
        cvv=os.getenv("cvv"),
        address_line_1=os.getenv("address_line_1"),
        address_line_2=os.getenv("address_line_2"),
        post_code=os.getenv("post_code"),
    )
    booker = BaFlightBooker()
    booker.run_search(params)
