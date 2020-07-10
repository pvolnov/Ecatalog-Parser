import re
import time

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
        if "#" in i.a['href']:
            print(i)
            continue
        item = {
            "keywords": [],
            "params": {}
        }
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
            price = i.find("div", {"class": "pr31 ib"}).span.text.replace("\xa0", "")
            item["min_price"] = price
            item["max_price"] = price
        item['name'] = i.a['title']
        item['category'] = catid
        item['url'] = "https://www.e-katalog.ru" + i.a['href']
        items.append(item)
    return items


def parse_category(catid):
    r = requests.get(f"https://www.e-katalog.ru/list/{catid}/")
    soup = BeautifulSoup(r.text, 'html5lib')
    n = int(re.search(r"\d+", soup.find("div", {"class": "page-title"}).text).group(0)) // 24
    res = []
    for page in tqdm(range(1, n)):
        r = requests.get(f"https://www.e-katalog.ru/list/84/{page}/")
        soup = BeautifulSoup(r.text, 'html5lib')
        res += parse_items(soup, catid)

    return res


def full_parse_item(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html5lib')
    item = {"keywords": [], "params": {}, "url": url, "name": soup.h1.text.replace("\xa0", " ")}

    if soup.find("span", {"itemprop": "lowPrice"}):
        item['min_price'] = soup.find("span", {"itemprop": "lowPrice"}).text.replace("\xa0", " ")
        item['max_price'] = soup.find("span", {"itemprop": "highPrice"}).text.replace("\xa0", " ")
    else:
        price = soup.find("span", {"price_marker": True}).text.replace("\xa0", " ")
        item['max_price'] = item['min_price'] = price

    for kw in soup.find_all("a", {"class": "ib no-u"}):
        item['keywords'].append(kw.text)

    for tr in soup.find_all(lambda tag: tag.name == "tr" and tag.find("img") is None and len(tag.find_all("td")) == 2):
        wds = tr.find_all("td")
        if wds[1].text.replace("\xa0", " ") != "":
            item['params'][wds[0].text.replace("\xa0", " ")] = wds[1].text.replace("\xa0", " ")

        if wds[0].text == "Цвет":
            item['params']["Цвет"] = wds[1].div['title']
    return item


if __name__ == "__main__":
    print("========START=========")
    while True:
        items = Items.select().where(Items.done == False).execute()
        for i in tqdm(items):
            try:
                item = full_parse_item(i.url)
            except Exception as e:
                print(e, i.url)
                continue
            i.done = True
            i.keywords = item['keywords']
            i.params = item['params']
            i.min_price = item['min_price']
            i.max_price = item['max_price']
            i.name = item['name']
            i.save()

        items = Items.select().where((Items.done == True) & (Items.sended == False)).execute()
        items = [model_to_dict(item) for item in items]

        if len(items) > 0:
            for i in items:
                i.update(i['params'])
                i['keywords'] = ";".join(i['keywords'])
                del i['params']
                del i['category']
                del i['id']
                del i['done']
                del i['sended']

            d = pd.DataFrame.from_dict(items)
            d.to_excel("data.xlsx")
            for u in Users.select().execute():
                with open("data.xlsx", "rb") as f:
                    bot.send_document(u.tel_id, f, caption="Вкаченные товары")

            Items.update({Items.sended: True}).where(Items.done == True).execute()
        time.sleep(20)
