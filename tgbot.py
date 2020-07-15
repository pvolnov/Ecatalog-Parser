import re

import pandas as pd
import telebot
from telebot import types

import config
from config import TG_BOT_APY_KEY
from models import Items, Users, DialogState
from monitor import parse_category


class btns:
    PARSE_ITEMS = "Скачать товары по прямым ссылкам ⬇️"
    PARSE_CATEGORIES = "Выкачать все товары с категории 🗳"
    PARSE_CATEGORIES_LITE = "Выкачать товары по превью с категорий 🔗"


bot = telebot.TeleBot(TG_BOT_APY_KEY)

parsels_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                             one_time_keyboard=True,
                                             row_width=1)
parsels_keyboard.add(
    types.KeyboardButton(text=btns.PARSE_ITEMS),
    types.KeyboardButton(text=btns.PARSE_CATEGORIES),
    types.KeyboardButton(text=btns.PARSE_CATEGORIES_LITE),
)


@bot.message_handler(commands=['start', 'menu', 'status'])
def start(message):
    if message.text == "/start":
        bot.send_message(message.chat.id, "Пришлите пароль для активации бота")
    elif message.text == "/menu":
        user = Users.get(Users.tel_id == message.chat.id)
        user.dstat = DialogState.AUTH
        user.save()
        bot.send_message(message.chat.id, "Главное меню", reply_markup=parsels_keyboard)

    elif message.text == "/status":
        will_load = Items.select().where(Items.done == False).count()
        loaded = Items.select().where((Items.done == True) & (Items.sended == False)).count()

        bot.send_message(message.chat.id, f"Сохранено {loaded}/{loaded + will_load}")


@bot.message_handler(content_types=['document'])
def new_doc(message):
    try:
        user = Users.get(Users.tel_id == message.chat.id)
        if user.dstat == DialogState.AUTH:
            bot.send_message(message.chat.id, "Укажите тип парсинга")
            return

        print("Mew doc", user.dstat)
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open("file.xlsx", "wb") as f:
            f.write(downloaded_file)
        data = pd.read_excel("file.xlsx")
        urls = list(data["Ссылка"])

        dstat = user.dstat
        user.dstat = DialogState.AUTH
        user.save()

        if dstat == DialogState.PARSE_ITEMS:
            items = [{"url": u} for u in urls]
        else:
            items = []
            bot.send_message(message.chat.id, f"Начали собирать товары с {len(urls)} категорий")
            for u in urls:
                catid = re.search(r"\d+", u)
                if catid:
                    items += parse_category(catid.group(0))
                    print("items", len(items))
                else:
                    bot.send_message(message.chat.id, f"Некорректная ссылка на категорию: {u}\n"
                                                      f"Ссылка на категорию должна заканчиваться на kXXX.htm, "
                                                      f"пример правильной ссылки: https://www.e-katalog.ru/k556.htm")
            if dstat == DialogState.PARSE_CATEGORIES_LITE:
                for i in items:
                    i['done'] = True

        urls = [i['url'] for i in items]
        Items.delete().where(Items.url.in_(urls)).execute()
        Items.insert_many(items).execute()

        bot.reply_to(message, f'Sucsessfully added {len(items)} items', reply_markup=parsels_keyboard)

    except Exception as e:
        bot.reply_to(message, f'Error: {e}', reply_markup=parsels_keyboard)


@bot.message_handler(content_types=["text"])
def text_mes(message):
    if message.text == config.TG_BOT_PASW:
        if Users.get_or_none(Users.tel_id == message.chat.id) is None:
            Users.create(tel_id=message.chat.id,
                         name=str(message.from_user.first_name) + " " + str(message.from_user.last_name))
        bot.send_message(message.chat.id, "Бот активирован", reply_markup=parsels_keyboard)
        return

    user = Users.get_or_none(Users.tel_id == message.chat.id)
    if user is None:
        bot.send_message(message.chat.id, "Неверный пароль!")
        return

    if message.text == btns.PARSE_ITEMS:
        user.dstat = DialogState.PARSE_ITEMS

    elif message.text == btns.PARSE_CATEGORIES:
        user.dstat = DialogState.PARSE_CATEGORIES

    elif message.text == btns.PARSE_CATEGORIES_LITE:
        user.dstat = DialogState.PARSE_CATEGORIES_LITE
    else:
        bot.send_message(message.chat.id, "Команда не найдена")
        return

    user.save()
    bot.send_message(message.chat.id,
                     "Пришлите документ в формате <b>.xlsx</b> с колонкой 'Ссылка' или нажмите /menu для отмены.",
                     parse_mode="HTML")


if __name__ == "__main__":
    print("========START=========")
    bot.polling(none_stop=True, timeout=60)
