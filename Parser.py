import re
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from tqdm import tqdm
import config
from models import TaskStatus, Items, Users


class Parser:
    modal_accept = 0

    def __init__(self, SELENOID_ADRESS, SELENOID_PROXY):
        print("connect to selenoid begin")
        self.driver = webdriver.Remote(
            command_executor=SELENOID_ADRESS,
            desired_capabilities={
                "browserName": "chrome",
                "sessionTimeout": "2h"
            }
        )
        print("connected")
        self.SELENOID_PROXY = SELENOID_PROXY
        self.ozon_cookies = self.get_ozon_cookies()

    def parse_wileberrise(self, url):
        item_id = re.search(r'\d+', url).group(0)
        info = requests.get('https://nm-2-card.wildberries.ru/enrichment/v1/api?spp=0',
                            params={"nm": item_id}).json()["data"]['products'][0]
        return {
            "price": info['salePrice'],
            "stars": info["rating"],
            "review": info["feedbackCount"],
            "brand": info["brand"],
            "color": ";".join([c['name'] for c in info["colors"]]),
            "stock": sum(
                sum(q['qty'] for q in s['stocks'])
                for s in info['sizes'])
        }

    def pass_beru_captcha(self, page):
        if "captcha" in page:
            print("Find captcha")
            soup = BeautifulSoup(page, 'html5lib')
            photo = requests.get(soup.img['src'])
            files = {'file': ('captcha.jpg', photo.content)}
            task_id = requests.post("https://rucaptcha.com/in.php",
                                    data={
                                        "key": config.RU_CAPTCHA_APY_KEY
                                    }, files=files
                                    ).text[3:]

            print(f"Get captcha ID {task_id}")
            captcha_text = ""
            while "OK" not in captcha_text:
                time.sleep(2)
                captcha_text = requests.get("https://rucaptcha.com/res.php",
                                            params={
                                                "key": config.RU_CAPTCHA_APY_KEY,
                                                "action": "get",
                                                "id": task_id
                                            }).text
            captcha_text = captcha_text[3:]
            print(f"Get captcha result: {captcha_text}")
            self.driver.find_element_by_class_name("input-wrapper__content").send_keys(captcha_text)
            self.driver.find_element_by_class_name("submit").click()
            time.sleep(2)
            return "captcha" not in self.driver.page_source
        return True

    def get_ozon_cookies(self):
        self.driver.get("https://ozon.ru")
        cookies = self.driver.get_cookies()
        return {c['name']: c['value'] for c in cookies}

    def parse_ozon(self, url):
        while True:
            r = requests.get(url,
                             cookies=self.ozon_cookies,
                             proxies={
                                 'all': self.SELENOID_PROXY
                             })
            if "ROBOTS" in r.text:
                self.ozon_cookies = self.get_ozon_cookies()
                print("Reset")
            else:
                break

        soup = BeautifulSoup(r.text, 'html5lib')
        data = {
            "brand": "-",
            "color": "-",
            "stars": 0,
            "review": 0,
        }

        review = soup.find("a", {"href": lambda x: x and "reviews" in x})
        if review:
            data["review"] = re.search(r"\d+", review.text).group(0)
            data['stars'] = review.parent.div['title']

        brend = soup.find(lambda tag: tag.name == "div" and "Бренд" in tag.next)
        if brend:
            data["brand"] = brend.span.text

        if soup.title and re.search(r"\d+ шт", soup.title.text):
            data["stock"] = re.search(r"\d+ шт", soup.title.text).group(0)[:-3]
        elif soup.find(lambda tag: tag.name == "div" and "Товар закончился" in tag.next):
            data["stock"] = 0
        else:
            data["stock"] = 9999

        price = soup.find(lambda tag: tag.name == "span" and re.match(r".*₽\s+$", tag.text)).text
        if price:
            data["price"] = re.sub(r"\D", "", price)

        color = soup.find(lambda tag: tag.name == "span" and "Цвет" in tag.text)
        if color:
            data["color"] = color.find_all("span")[-1].text

        return data

    def parse_beru(self, url):
        def get_int(s):
            return re.search(r"\d+", s).group(0)

        self.driver.get(url)
        page = self.driver.page_source

        while not self.pass_beru_captcha(page):
            pass

        soup = BeautifulSoup(page, 'html5lib')

        data = {
            "brand": "-",
            "color": "-",
            "stars": 0,
            "review": 0,
            "sold": 0,
            "stock": 9999,
        }
        sold = re.search(r"\d+ человека? купили", page)
        if sold:
            data["sold"] = get_int(sold.group(0))
        data["price"] = soup.find("span", {"data-tid": "c3eaad93"}).text.replace(" ", "")
        data["stars"] = get_int(
            soup.find(lambda tag: tag.name == "div" and tag.has_attr('style') and len(tag.find_all("span")) == 5)[
                'style'])

        if re.search(r"\d+&nbsp;отзыв", page):
            data["review"] = get_int(re.search(r"\d+&nbsp;отзыв", page).group(0))

        if re.search(r"/brand/\w+?/", page):
            data["brand"] = re.search(r"/brand/\w+?/", page).group(0).split("/")[2]
        elem = soup.find(lambda tag: tag.name == "span" and tag and "Цвет товара" in tag.text)
        if elem:
            data["color"] = elem.find_next_sibling().text

        return data

    def execute_task(self, t: Items):
        if t.shop == "wilberries":
            dat = self.parse_wileberrise(t.url)
        elif t.shop == "ozon":
            dat = self.parse_ozon(t.url)
        elif t.shop == "beru":
            dat = self.parse_beru(t.url)
        else:
            print("Unknown shop",t.shop)

        if t.shop == "beru":
            t.sold = dat["sold"]
        elif t.shop == "wilberries" and t.status == TaskStatus.FOR_LOAD:
            r = requests.get(t.url)
            count = re.search(r"ordersCount\":\d+", r.text)
            if count:
                t.sold = count.group(0).replace("ordersCount\":", "")
        else:
            t.sold += max(t.stock - dat["stock"], 0)

        t.price = dat["price"]
        t.stock = dat["stock"]
        t.stars = dat["stars"]
        t.review = dat["review"]
        t.brand = dat["brand"]
        t.color = dat["color"]

        if t.status == TaskStatus.FOR_LOAD:
            t.status = TaskStatus.LOAD_COMPLE
        else:
            t.status = TaskStatus.UPDATE_COMPLE
        t.save()
