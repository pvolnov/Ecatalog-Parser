from models import Items

# Items.update({Items.sended: False}).execute()
# Items.update({Items.sended: False}).where(Items.done == True).execute()
from monitor import parse_category, full_parse_item

print(full_parse_item('https://www.e-katalog.ru/XIAOMI-XIAOWA-E20.htm'))
