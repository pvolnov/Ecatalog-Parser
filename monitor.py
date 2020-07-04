import re
import time
from datetime import datetime

import pandas as pd
import telebot
from tqdm import tqdm

import config
from Parser import Parser
from models import Items, TaskStatus, Users

bot = telebot.TeleBot(config.TG_BOT_APY_KEY)


def send_records(items, caption=""):
    d = pd.DataFrame.from_dict(items)
    d.to_excel("data.xlsx")
    for u in Users.select().select().execute():
        with open("data.xlsx", "rb") as f:
            bot.send_document(u.tel_id, f, caption=caption)
            print(f"Sended to {u.tel_id}")


if __name__ == "__main__":
    print("========START=========")
    ps = Parser(config.SELENOID_ADRESS, config.SELENOID_PROXY)

    while True:
        items = Items.select().where(
            (Items.status == TaskStatus.FOR_UPDATE) | (Items.status == TaskStatus.FOR_LOAD)).execute()
        print('items', len(items))

        for i in tqdm(items):
            try:
                ps.execute_task(i)
            except Exception as e:
                print(e)

            if i.status == TaskStatus.FOR_LOAD:
                i.status = TaskStatus.LOAD_COMPLE
            else:
                i.status = TaskStatus.UPDATE_COMPLE
            i.save()

        updated_done = False
        for shop in ["wilberries", "ozon", "beru"]:
            items_loads = Items.select().where((Items.shop == shop)
                                               & (Items.status == TaskStatus.LOAD_COMPLE)).execute()
            if len(items_loads) > 0:
                items_loads = [{
                    "Бренд": i.brand,
                    "Ссылка": i.url,
                    "Артикул": re.search(r"\d+", i.url).group(0) if re.search(r"\d+", i.url) else "",
                    "Цена": i.price,
                    "Количество заказов": i.sold,
                    "Цвет": i.color,
                    "Колисество отзывов": i.review,
                    "Рейтинг": i.stars,
                } for i in items_loads]

                send_records(items_loads, f"Выкаченные с {shop} товары ({len(items_loads)})")
                updated_done = True

            items_update = Items.select().where((Items.shop == shop)
                                                & (Items.status == TaskStatus.UPDATE_COMPLE)).execute()
            if len(items_update) > 0:
                items_update = [{
                    "Ссылка": i.url,
                    "Артикул": re.search(r"\d+", i.url).group(0) if re.search(r"\d+", i.url) else "",
                    "Цена": i.price,
                    "Остаток": i.stock,
                    "Продано": i.sold,
                } for i in items_update]
                send_records(items_update, f"Ежеднеаное обновление товаров с "
                                           f"{shop} ({datetime.now().strftime('%d.%m')})")
                updated_done = True

        if updated_done:
            Items.update({Items.status: TaskStatus.UPDATE_SUSPENDED}).where(
                Items.status == TaskStatus.UPDATE_COMPLE).execute()

            Items.delete().where(Items.status == TaskStatus.LOAD_COMPLE).execute()

        if datetime.now().strftime("%H:%M") == "06:00":
            print("New cycle begin")
            Items.update({Items.status: TaskStatus.FOR_UPDATE}).where(
                Items.status.status == TaskStatus.UPDATE_SUSPENDED).execute()
            time.sleep(60)

        time.sleep(40)
        ps.step()
