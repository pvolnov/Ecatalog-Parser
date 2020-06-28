## Ozon + Beru + Wilberries Parser with telegram bot admin

Монитор информации товаров с сайтов магазинов с управление через telegram бота.

### Инструкция пользования 
1. Регистируемся в telegram bote, отправляя пароль `admin88r`
2. Выбираем категорию товаров из списка вариантов
3. Отправляем докумен `...xlsx`, сожержащий колонку _Ссылка_ с прямой ссылкой на товар без дополнительных параметров. Обратите внимание, что в одном файле __не может быть__ товары из разных магазинов.
    * https://beru.ru/product/vneshnii-hdd-seagate-expansion-portable-drive-1-tb-chernyi/100324823735?show-uid=15933702781033344189506001&offerid=D0Nfj-FCALyvCH1Ma973Fw - НЕ ВЕРНО
    * https://beru.ru/product/vneshnii-hdd-seagate-expansion-portable-drive-1-tb-chernyi/100324823735 - ВЕРНО
4. Для отслеживания сосояния парсера можно вызывать команду `/status`

### Настройка

1. Получаем `telegram_bot_key` и заменяем его в фале `config.py`
2. Получаем `ru_captcha_key` и заменяем его в фале `config.py`
3. Ставим зависимости из файла `requirements.txt`: `pip install -r requirements.txt`
4. Запускаем telegram bot: `python3 tgbot.py`
5. Запускаем monitor: `python3 monitor.py`