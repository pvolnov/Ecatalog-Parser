import re
import time
from datetime import datetime

import pandas as pd
import requests
import telebot
from tqdm import tqdm

from config import *
from models import Items, TaskStatus, Users, DialogState

bot = telebot.TeleBot(telegram_bot_key)


def parse_wileberrise(url):
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


def send_records(items, caption=""):
    d = pd.DataFrame.from_dict(items)
    d.to_excel("data.xlsx")
    with open("data.xlsx", "rb") as f:
        for u in Users.select().select().execute():
            bot.send_document(u.tel_id, f, caption=caption)


if __name__ == "__main__":
    tasks = Items.select().where((Items.status == TaskStatus.FOR_UPDATE) |
                                 (Items.status == TaskStatus.FOR_LOAD)).execute()
    for t in tqdm(tasks):
        dat = parse_wileberrise(t.url)
        t.price = dat["price"]
        t.sold += max(t.stock - dat["stock"], 0)
        t.stock = dat["stock"]
        t.stars = dat["stars"]
        t.review = dat["review"]
        t.brand = dat["brand"]
        t.color = dat["color"]

        if t.status == TaskStatus.FOR_LOAD:
            r = requests.get(t.url)
            count = re.search(r"ordersCount\":\d+", r.text)
            if count:
                t.sold = count.group(0).replace("ordersCount\":", "")
            t.status = TaskStatus.LOAD_COMPLE
        else:
            t.status = TaskStatus.UPDATE_COMPLE
        t.save()

    items_loads = Items.select().where(Items.status == TaskStatus.LOAD_COMPLE).execute()
    if len(items_loads) > 0:
        items_loads = [{
            "Бренд": i.brand,
            "Ссылка": i.url,
            "Артикул": re.search(r"\d+", i.url).group(0),
            "Цена": i.price,
            "Количество заказов": i.sold,
            "Цвет": i.color,
            "Колисество отзывов": i.review,
            "Рейтинг": i.stars,
        } for i in items_loads]

        send_records(items_loads, f"Выкаченные с wildberries товары ({len(items_loads)})")
        Items.delete().where(Items.status == TaskStatus.LOAD_COMPLE).execute()

    items_update = Items.select().where(Items.status == TaskStatus.UPDATE_COMPLE).execute()
    if len(items_update) > 0:
        items_update = [{
            "Ссылка": i.url,
            "Артикул": re.search(r"\d+", i.url).group(0),
            "Цена": i.price,
            "Остаток": i.stock,
            "Продано": i.sold,
        } for i in items_update]
        send_records(items_update, f"Ежеднеаное обновление товаров с "
                                   f"wildberries ({datetime.now().strftime('%d.%m')})")

    if datetime.now().strftime("%H:%M") == "00:00":
        print("Items was deleted")
        Items.update({Items.status: TaskStatus.FOR_UPDATE}).where(
            Items.status.status == TaskStatus.UPDATE_COMPLE).execute()
        time.sleep(60)
    time.sleep(10)
