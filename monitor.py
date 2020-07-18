import re
import time
import traceback

import pandas as pd
import requests
import telebot
from bs4 import BeautifulSoup
from playhouse.shortcuts import model_to_dict
from tqdm import tqdm

import config
from models import Items, Users

bot = telebot.TeleBot(config.TG_BOT_APY_KEY)


def parse_items(soup, catid):
    items = []
    for i in soup.find_all("table", {"class": "model-short-block"}):
        item = {
            "keywords": [],
            "params": {},
            "external_url": False
        }

        if "#" in i.a['href']:
            href = re.search(r"https://www.e-katalog.ru/clcp.+?\"", str(soup)).group(0)[:-1]
            item['external_url'] = True
        else:
            href = "https://www.e-katalog.ru" + i.a['href']

        for p in i.find_all("div", {"title": True}):
            wds = p.text.replace("\xa0", " ").split(":")
            if len(wds) > 1:
                item["params"][wds[0]] = wds[1]

        for kw in i.find_all("a", {"class": "ib no-u"}):
            item['keywords'].append(kw.text)

        price = i.find("div", {"class": "model-price-range"})
        if price:
            price = price.find_all("span")
            item["min_price"] = price[0].text.replace("\xa0", "")
            item["max_price"] = price[1].text.replace("\xa0", "")
        else:
            price = i.find("div", {"class": "pr31 ib"})
            if price and price.span:
                price = price.span.text.replace("\xa0", "")
                item["min_price"] = price
                item["max_price"] = price

        item['name'] = i.a['title']
        item['category'] = catid
        item['url'] = href
        items.append(item)
    return items


def parse_category(catid):
    r = requests.get(f"https://www.e-katalog.ru/list/{catid}/")
    soup = BeautifulSoup(r.text, 'html5lib')
    n = int(re.search(r"\d+", soup.find("div", {"class": "page-title"}).text).group(0)) // 24 + 1
    res = []
    for page in tqdm(range(0, n)):
        r = requests.get(f"https://www.e-katalog.ru/list/{catid}/{page}/")
        soup = BeautifulSoup(r.text, 'html5lib')
        res += parse_items(soup, catid)

    return res


def full_parse_item(url):
    name = url.split("/")[-1].replace(".htm", "")

    r = requests.get("https://www.e-katalog.ru/ek-item.php", params={
        "resolved_name_": name,
        "view_": "tbl"
    })

    soup = BeautifulSoup(r.text, 'html5lib')
    item = {"keywords": [], "params": {}, "url": url,
            # "name": soup.h1.text.replace("\xa0", " ").replace("Характеристики и описание", "")
            }

    if soup.find("span", {"itemprop": "lowPrice"}):
        item['min_price'] = soup.find("span", {"itemprop": "lowPrice"}).text.replace("\xa0", " ")
        item['max_price'] = soup.find("span", {"itemprop": "highPrice"}).text.replace("\xa0", " ")
    else:
        price = soup.find("span", {"price_marker": True}).text.replace("\xa0", " ")
        item['max_price'] = item['min_price'] = price

    for kw in soup.find_all("a", {"class": "ib no-u"}):
        item['keywords'].append(kw.text)

    for tr in soup.find_all(lambda tag: tag.name == "tr" and len(tag.find_all("td")) == 2):
        wds = tr.find_all("td")
        if not wds[1].img:
            if "vote" not in wds[0].text:
                val = ""
                for elem in wds[1].contents:
                    if isinstance(elem, str):
                        val += elem.replace("\xa0", " ")
                    else:
                        val += "\n"

                if re.search(r"\S", val):
                    item['params'][wds[0].text.replace("\xa0", " ")] = val
        elif "function" not in wds[0].text:
            item['params'][wds[0].text.replace("\xa0", " ")] = "+"

        if wds[0].text == "Цвет":
            item['params']["Цвет"] = wds[1].div['title']
    return item


if __name__ == "__main__":
    print("========START=========")

    while True:
        items = Items.select().where(Items.done == False).limit(1000).execute()
        for i in tqdm(items):
            if i.external_url:
                i.done = True
                i.save()
                continue

            try:
                item = full_parse_item(i.url)
            except Exception as e:
                print(e, i.url)
                traceback.print_exc()
                continue

            i.keywords = item['keywords']
            i.params = item['params']
            i.min_price = item['min_price']
            i.max_price = item['max_price']
            i.done = True
            i.save()

        if Items.select().where(Items.done == False).count() > 0:
            continue

        items = Items.select().where((Items.done == True) & (Items.sended == False)).limit(1000).execute()
        iurl = [i.url for i in items]
        items = [model_to_dict(item) for item in items]

        if len(items) > 0:
            for i in tqdm(items):
                i.update(i['params'])
                for p in i['params']:
                    if i['params'][p] == "":
                        del i[p]

                i['keywords'] = "; ".join(i['keywords'])
                if i['external_url']:
                    i["Внешняя ссылка"] = "ДА"
                del i['params']
                del i['external_url']
                del i['category']
                del i['id']
                del i['done']
                del i['sended']

            d = pd.DataFrame.from_dict(items)
            d.to_excel("data.xlsx")
            for u in Users.select().execute():
                with open("data.xlsx", "rb") as f:
                    bot.send_document(u.tel_id, f, caption="Вкаченные товары")

            Items.update({Items.sended: True}).where(Items.url.in_(iurl)).execute()
        time.sleep(20)
