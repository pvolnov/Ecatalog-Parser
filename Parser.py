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
                "sessionTimeout": "5m"
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

    def get_captcha_ans(self, filename="captcha.png"):
        with open(filename, "rb") as f:
            task_id = requests.post("https://rucaptcha.com/in.php",
                                    data={
                                        "key": config.RU_CAPTCHA_APY_KEY
                                    }, files={"file": f}
                                    ).text[3:]

        print(f"Get captcha ID {task_id}")
        captcha_text = ""
        while "OK" not in captcha_text:
            time.sleep(3)
            captcha_text = requests.get("https://rucaptcha.com/res.php",
                                        params={
                                            "key": "3e12df6ed3a4c0e9e7b2c951bb2c9c51",
                                            "action": "get",
                                            "id": task_id
                                        }).text
            if captcha_text == "ERROR_CAPTCHA_UNSOLVABLE":
                return False, task_id

        captcha_text = captcha_text[3:]
        print(f"Get captcha result: {captcha_text}")
        return captcha_text, task_id

    def pass_beru_captcha(self, page):
        if "captcha" in page:
            print("Find captcha")
            self.driver.find_element_by_tag_name("img").screenshot("captcha.png")

            captcha_text, task_id = self.get_captcha_ans()
            if not captcha_text:
                return self.pass_beru_captcha(page)

            self.driver.find_element_by_class_name("input-wrapper__content").send_keys(captcha_text)
            self.driver.find_element_by_class_name("submit").click()
            time.sleep(2)
            if "captcha" in self.driver.page_source:
                r = requests.get("https://rucaptcha.com/res.php",
                                 params={
                                     "key": config.RU_CAPTCHA_APY_KEY,
                                     "action": "reportbad",
                                     "id": task_id
                                 })
                print("recaptcha is incorrect:", r.text)
                time.sleep(2)
                return False

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

        captcha = False
        while not self.pass_beru_captcha(page):
            captcha = True
        if captcha:
            page = self.driver.page_source

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

    def step(self):
        self.driver.refresh()

    def execute_task(self, t: Items):
        if t.shop == "wilberries":
            dat = self.parse_wileberrise(t.url)
        elif t.shop == "ozon":
            dat = self.parse_ozon(t.url)
        elif t.shop == "beru":
            dat = self.parse_beru(t.url)
        else:
            print("Unknown shop", t.shop)
            return

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

        # if t.status == TaskStatus.FOR_LOAD:
        #     t.status = TaskStatus.LOAD_COMPLE
        # else:
        #     t.status = TaskStatus.UPDATE_COMPLE
        # t.save()

    def catalog_parse(self, cat_urls, shop):
        print(cat_urls, shop)

        urls = []
        for url in cat_urls:
            for i in range(1, 99):
                self.driver.get(f"{url}?page={i}")
                page = self.driver.page_source
                time.sleep(1)
                soup = BeautifulSoup(page, 'html5lib')
                if shop == "ozon":
                    urs = soup.find("div", {"class": "widget-search-result-container"}).find_all("a",
                                                                                                 {
                                                                                                     "class": "tile-hover-target"})
                    urs = ["https://www.ozon.ru" + a['href'].split("?")[0] for a in urs]
                    if len(urs) < 36:
                        break

                elif shop == "beru":

                    captcha = False
                    while not self.pass_beru_captcha(page):
                        captcha = True
                    if captcha:
                        time.sleep(2)
                        soup = BeautifulSoup(self.driver.page_source, 'html5lib')

                    urs = soup.find_all("a", {"href": lambda x: x and "product" in x})
                    urs = ["https://beru.ru" + a['href'].split("?")[0] for a in urs]
                    if len(urs) < 20:
                        break

                elif shop == 'wildberries':
                    urs = soup.find_all("a", {"class": "ref_goods_n_p j-open-full-product-card"})
                    urs = [a['href'] for a in urs]
                    if len(urs) == 0:
                        break
                else:
                    raise Exception("Invalid shop name")

                urls += list(set(urs))
        return urls
