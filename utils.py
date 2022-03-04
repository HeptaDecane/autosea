import os
import re
import enum
import time
import json
import requests
from uuid import uuid4
from pathlib import Path
from threading import Thread
from datetime import datetime
from selenium import webdriver
from pyvirtualdisplay import Display
from selenium.webdriver.common.keys import Keys

BASE_DIR = Path(__file__).resolve().parent
DIR = os.getcwd()
debug_port = 9222


class Response(enum.Enum):
    SUCCESS = 0
    FAILURE = 1
    TIMEOUT = 2


class TimeoutException(Exception):
    def __init__(self, message='timeout'):
        super(TimeoutException, self).__init__(message)


class Browser(Thread):
    def __init__(self, command, virtual=False):
        self.virtual = virtual
        self.command = command
        Thread.__init__(self)

    def run(self):
        if self.virtual:
            display = Display(visible=True, size=(1920, 1080))
            display.start()

        os.system(self.command)


class Bot:
    def __init__(self, driver_location, binary_location, user_data, virtual=False):
        self.collection_url = None
        self.store = None
        self.asset_url = None
        self.raise_exception = True

        command = 'google-chrome --remote-debugging-port={} --user-data-dir="{}"'.format(debug_port, user_data)

        options = webdriver.ChromeOptions()
        options.binary_location = binary_location
        options.add_experimental_option("debuggerAddress", "127.0.0.1:{}".format(debug_port))
        options.add_argument('--user-data-dir={}'.format(user_data))
        options.add_argument("--disable-blink-features=AutomationControlled")

        self.browser = Browser(command, virtual=virtual)
        self.browser.start()
        self.driver = webdriver.Chrome(executable_path=driver_location, options=options)
        self.driver.maximize_window()

    def load_captcha_solver(self):
        self.driver.execute_script("window.open('about:blank', 'solver');")
        self.driver.switch_to.window('solver')
        self.driver.get('https://azure.microsoft.com/en-us/services/cognitive-services/speech-to-text')
        time.sleep(5)

    def solve_captcha(self):
        target = self.locate_element('//iframe[@title="reCAPTCHA"]')
        self.driver.switch_to.frame(target)

        target = self.locate_element('//span[@id="recaptcha-anchor"]')
        target.click()

        self.driver.switch_to.default_content()

        target = self.locate_element('//iframe[@title="recaptcha challenge expires in two minutes"]')
        self.driver.switch_to.frame(target)

        time.sleep(1)
        self.locate_element('//button[@id="recaptcha-audio-button"]')
        self.driver.execute_script('document.getElementById("recaptcha-audio-button").click()')

        target = self.locate_element('//a[@class="rc-audiochallenge-tdownload-link"]')
        src = target.get_attribute('href')

        self.driver.switch_to.default_content()
        self.driver.switch_to.window('solver')
        self.driver.refresh()

        response = requests.get(src)
        fileid = ''.join(str(uuid4()).split('-'))
        file = open('audio/{}.mp3'.format(fileid), "wb")
        file.write(response.content)
        file.close()
        os.system('ffmpeg -i audio/{}.mp3 audio/{}.wav -y'.format(fileid, fileid))

        target = self.locate_element('//input[@id="punctuation"]')
        target.click()
        target = self.locate_element('//input[@id="fileinput"]')
        target.send_keys('{}/audio/{}.wav'.format(DIR, fileid))

        text = None
        while True:
            target = self.locate_element('//textarea[@id="speechout"]')
            text = target.get_attribute('value')
            if fileid in text and text.count('-') > 100:
                break

        for phrase in text.split('-'):
            if fileid not in phrase and '\n' in phrase:
                text = phrase.strip()
                break

        self.driver.switch_to.window('opensea')
        target = self.locate_element('//iframe[@title="recaptcha challenge expires in two minutes"]')
        self.driver.switch_to.frame(target)

        target = self.locate_element('//input[@id="audio-response"]')
        target.send_keys(text)

        time.sleep(1)
        self.locate_element('//button[@id="recaptcha-verify-button"]')
        self.driver.execute_script('document.getElementById("recaptcha-verify-button").click()')

        self.driver.switch_to.default_content()

    def access_collection(self, collection_url, wallet_password, store=None):
        self.store = store
        self.collection_url = collection_url
        self.asset_url = '{}asset/matic/0x2953399124f0cbb46d2cbacd8a89cf0599974963/{}/edit'.format(collection_url, '{}')

        ext = "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/home.html#unlock"

        # unlock wallet
        self.driver.execute_script("window.open('about:blank', 'wallet');")
        self.driver.switch_to.window("wallet")
        self.driver.get(ext)

        target = self.locate_element('//input[@class="MuiInputBase-input MuiInput-input"]', 'wallet password')
        target.send_keys(wallet_password)
        target = self.locate_element('//button[text()="Unlock"]', 'unlock wallet')
        target.click()
        time.sleep(5)

        # go to collection page
        self.driver.execute_script("window.open('about:blank', 'opensea');")
        self.driver.switch_to.window("opensea")
        self.driver.get(collection_url)
        time.sleep(5)
        self.driver.refresh()
        time.sleep(5)

        self.locate_element('//a[text()="Add item"]', 'add item')

    def locate_element(self, xpath, desc=None, index=0):
        start_time = time.time()
        print(xpath) if desc is None else print(desc)
        items = []
        while not items:
            current_time = time.time()
            try:
                items = self.driver.find_elements_by_xpath(xpath)
            except Exception as e:
                print(e)
    
            if current_time - start_time > 30:
                if self.raise_exception:
                    TimeoutException()
                else:
                    os.system('notify-send "Exception" "{}"'.format(desc))
                    start_time = current_time
    
        return items[index]

    def locate_elements(self, xpaths, desc=None, index=0):
        if desc:
            print(desc)

        start_time = time.time()
        while True:
            current_time = time.time()

            for xpath in xpaths:
                target = self.driver.find_elements_by_xpath(xpath)
                if target:
                    print(xpath)
                    return target[index], xpaths.index(xpath)

            if current_time - start_time > 30:
                if self.raise_exception:
                    TimeoutException()
                else:
                    os.system('notify-send "Timeout" "{}"'.format(desc))
                    start_time = current_time

    def sign_or_reject(self, delay=0):
        start_time = time.time()
        print("sign_or_reject")

        self.driver.switch_to.window("wallet")
        self.locate_element('//div[contains(text(),"Queue")]')
        time.sleep(delay)
        self.driver.refresh()

        while True:
            current_time = time.time()
            targets = self.driver.find_elements_by_xpath('//button[text()="Sign"]')
            if targets:
                print('sign')
                target = self.locate_element('//div[@class="signature-request-message__scroll-button"]')
                target.click()
                time.sleep(delay)
                targets[0].click()
                self.driver.switch_to.window("opensea")
                return

            targets = self.driver.find_elements_by_xpath('//button[text()="Reject"]')
            if targets:
                print('reject')
                targets[0].click()
                self.driver.switch_to.window("opensea")
                return

            if current_time - start_time > 30:
                if self.raise_exception:
                    TimeoutException()
                else:
                    os.system('notify-send "Exception" "sign_or_reject"')
                    start_time = current_time

    def detect_captcha(self):
        start_time = time.time()
        while True:
            current_time = time.time()
            target = self.driver.find_elements_by_xpath('//h4[text()="Almost done"]')
            if target:
                os.system('notify-send "Captcha" "detected"')
                return True
    
            target = self.driver.find_elements_by_xpath('//h4[text()="Please wait..."]')
            if target:
                return False
    
            if current_time - start_time > 30:
                if self.raise_exception:
                    TimeoutException()
                else:
                    os.system('notify-send "Timeout" "captcha"')
                    start_time = current_time

    def select_media(self, filename, delay=0.0):
        target = self.locate_element('//input[@id="media"]', 'media')
        target.send_keys(self.store + filename)
        time.sleep(delay)

    def add_name(self, name, delay=0.0):
        target = self.locate_element('//input[@id="name"]', 'name')
        target.send_keys(name)
        time.sleep(delay)
    
    def add_description(self, desc, delay=0.0):
        target = self.locate_element('//textarea[@id="description"]', 'description')
        target.send_keys(desc)
        time.sleep(delay)
    
    def add_properties(self, props, delay=0.0):
        target = self.locate_element('//button[@aria-label="Add properties"]', 'add properties')
        target.click()
        time.sleep(delay)
    
        for key in props:
            target = self.locate_element('//input[@aria-label="Provide the property name"]', index=-1)
            target.send_keys(key)
            time.sleep(delay)
    
            target = self.locate_element('//input[@aria-label="Provide the property value"]', index=-1)
            target.send_keys(props[key])
            time.sleep(delay)
    
            target = self.locate_element('//button[text()="Add more"]', 'add more')
            target.click()
            time.sleep(delay)
    
        target = self.locate_element('//button[@aria-label="Remove Trait"]', index=-1)
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Save"]', 'save props')
        target.click()
        time.sleep(delay)
    
    def add_levels(self, levels, delay=0.0):
        target = self.locate_element('//button[@aria-label="Add levels"]', 'add levels')
        target.click()
        time.sleep(delay)
    
        for key in levels:
            target = self.locate_element('//input[@aria-label="Provide the numeric trait name"]', index=-1)
            target.send_keys(key)
            time.sleep(delay)
    
            target = self.locate_element('//input[@aria-label="Provide the max number of the numeric trait"]', index=-1)
            target.send_keys(Keys.CONTROL, 'a')
            target.send_keys(levels[key][1])
            time.sleep(delay)
    
            target = self.locate_element('//input[@aria-label="Provide the min number of the numeric trait"]', index=-1)
            target.send_keys(Keys.CONTROL, 'a')
            target.send_keys(levels[key][0])
            time.sleep(delay)
    
            target = self.locate_element('//button[text()="Add more"]', 'add more')
            target.click()
            time.sleep(delay)
    
        target = self.locate_element('//button[@aria-label="Remove Button"]', index=-1)
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Save"]', 'save levels')
        target.click()
        time.sleep(delay)
    
    def add_stats(self, stats, delay=0.0):
        target = self.locate_element('//button[@aria-label="Add stats"]', 'add stats')
        target.click()
        time.sleep(delay)
    
        for key in stats:
            target = self.locate_element('//input[@aria-label="Provide the numeric trait name"]', index=-1)
            target.send_keys(key)
            time.sleep(delay)
    
            target = self.locate_element('//input[@aria-label="Provide the max number of the numeric trait"]', index=-1)
            target.send_keys(Keys.CONTROL, 'a')
            target.send_keys(stats[key][1])
            time.sleep(delay)
    
            target = self.locate_element('//input[@aria-label="Provide the min number of the numeric trait"]', index=-1)
            target.send_keys(Keys.CONTROL, 'a')
            target.send_keys(stats[key][0])
            time.sleep(delay)
    
            target = self.locate_element('//button[text()="Add more"]', 'add more')
            target.click()
            time.sleep(delay)
    
        target = self.locate_element('//button[@aria-label="Remove Button"]', index=-1)
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Save"]', 'save stats')
        target.click()
        time.sleep(delay)
    
    def add_unlockable(self, secret, delay=0.0):
        target = self.locate_element('//input[@id="unlockable-content-toggle"]', 'unlockable')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element(
            '//textarea[@placeholder="Enter content (access key, code to redeem, link to a file, etc.)"]')
        target.send_keys(secret)
        time.sleep(delay)
    
    def list_item(self, price, extend_listing=False, delay=0.0):
        target = self.locate_element('//a[text()="Sell"]', 'sell')
        target.click()
        time.sleep(delay)
    
        if extend_listing:
            target = self.locate_element('//i[@value="calendar_today"]')
            target.click()
            time.sleep(delay)
    
            target = self.locate_element('//input[@type="date"]', index=-1)
            target.click()
            time.sleep(delay)
    
            now = datetime.now()
            date = min(30, int(now.strftime("%d")))
            month_6 = int(now.strftime("%m")) + 6
    
            target.send_keys('%02d' % date)
            target.send_keys(Keys.ARROW_RIGHT)
            target.send_keys('%02d' % month_6)
            time.sleep(delay)
    
        target = self.locate_element('//input[@placeholder="Amount"]', 'amount')
        target.send_keys('{}'.format(price))
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Complete listing"]', 'complete listing')
        target.click()
        time.sleep(delay)
    
    def sign(self, delay=0.0):
        target = self.locate_element('//button[text()="Sign"]', 'sign')
        target.click()
        time.sleep(delay)
    
        self.driver.switch_to.window("wallet")
        target = self.locate_element('//h2[text()="Signature Request"]')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Sign"]', 'metamask sign')
        target.click()
        time.sleep(delay)
    
        self.driver.switch_to.window("opensea")
        target = self.locate_element('//h4[text()="Your NFT is listed!"]')
        target.click()
        time.sleep(delay)

    def sign_message(self, delay=0.0):
        self.driver.switch_to.window("wallet")
        target = self.locate_element('//h2[text()="Signature Request"]')
        target.click()
        time.sleep(delay)

        target = self.locate_element('//button[text()="Sign"]', 'metamask sign')
        target.click()
        time.sleep(delay)

        self.driver.switch_to.window("opensea")
    
    def freeze_metadata(self, delay=0.0):
        target = self.locate_element('//input[@id="freezeMetadata"]', 'freeze switch')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Freeze"]', 'freeze btn')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//input[@name="freezeMetadataConsent"]', 'freeze checkbox')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Confirm"]', 'freeze btn')
        target.click()
        time.sleep(delay)

    def sign_transaction(self, delay=0.0):
        self.driver.switch_to.window("wallet")
        target = self.locate_element('//h2[text()="Signature Request"]')
        target.click()
        time.sleep(delay)

        target = self.locate_element('//div[@class="signature-request-message__scroll-button"]')
        target.click()
        time.sleep(delay)
    
        target = self.locate_element('//button[text()="Sign"]', 'metamask sign')
        target.click()
        time.sleep(delay)
    
        self.driver.switch_to.window("opensea")

    def reload(self):
        self.driver.refresh()
        time.sleep(5)
    
    def wait_for_progress(self, delay=0):
        print("wait_for_progress")
        start_time = time.time()
        while True:
            current_time = time.time()
            success = self.driver.find_elements_by_xpath('//div[text()="Complete"]')
            if success:
                time.sleep(delay)
                print(Response.SUCCESS)
                return Response.SUCCESS
    
            failure = self.driver.find_elements_by_xpath('//i[@value="error"]')
            if failure:
                time.sleep(delay)
                print(Response.FAILURE)
                return Response.FAILURE
    
            if current_time - start_time > 300:
                print(Response.TIMEOUT)
                return Response.TIMEOUT

    def collect_links(self, url, links_file):
        try:
            file = open(links_file, 'r')
            links = json.load(file)
        except FileNotFoundError:
            links = []

        self.driver.get(url)
        time.sleep(5)

        while True:
            try:
                anchors = self.driver.find_elements_by_xpath('//a[@ class="styles__StyledLink-sc-l6elh8-0 ikuMIO Blockreact__Block-sc-1xf18x6-0 kdnPIp AccountLink--ellipsis-overflow"]')
            except Exception as e:
                anchors = []
                print(e)

            for i in range(len(anchors)):
                try:
                    link = anchors[i].get_attribute('href')
                    if i % 2 != 0 and link not in links:
                        links.append(link)
                        print(link)
                except Exception as e:
                    print(e)
            json.dump(links, open(links_file, 'w'), indent=2)
            time.sleep(1)

    def collect_address(self, links_file, address_file, offset_file):
        try:
            file = open(links_file, 'r')
            links = json.load(file)
        except FileNotFoundError:
            links = []

        try:
            file = open(address_file, 'r')
            addresses = json.load(file)
        except FileNotFoundError:
            addresses = []

        try:
            file = open(offset_file, 'r')
            offset = json.load(file)
            start = offset['start']
        except FileNotFoundError:
            offset = {'start': 0}
            start = offset['start']

        end = len(links)

        while start < end:
            self.driver.get(links[start])
            try:
                match = re.search('\"wallet_accountKey\":{\"address\":\"\w{42}\"}', self.driver.page_source)
                match = re.search('0x\w{40}', match.group())
                address = match.group()
                if address not in addresses:
                    addresses.append(address)
                    json.dump(addresses, open(address_file, 'w'), indent=2)
            except Exception as e:
                print(e)

            print('{}/{}'.format(start, end), links[start])

            start += 1
            offset['start'] = start
            json.dump(offset, open(offset_file, 'w'), indent=2)
