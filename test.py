from models import Items

# Items.update({Items.sended: False}).execute()
# Items.update({Items.sended: False}).where(Items.done == True).execute()
from monitor import parse_category


print(len(parse_category('268')))
