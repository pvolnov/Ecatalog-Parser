from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase, ArrayField, JSONField
from enum import Enum
from config import bdname, bduser, bdpassword, bdport, bdhost

db = PostgresqlExtDatabase(bdname, user=bduser, password=bdpassword,
                           host=bdhost, port=bdport)


class DialogState:
    AUTH = 0
    PARSE_ITEMS = 1
    PARSE_CATEGORIES = 2
    PARSE_CATEGORIES_LITE = 3


class Items(Model):
    url = TextField()
    name = TextField(default="")
    category = IntegerField(default=-1)
    min_price = TextField(default="-")
    max_price = TextField(default="-")
    keywords = ArrayField(TextField, default=[])
    params = JSONField(default={})
    done = BooleanField(default=False)
    sended = BooleanField(default=False)

    class Meta:
        database = db


class Users(Model):
    name = TextField(default="")
    tel_id = BigIntegerField(unique=True)
    dstat = IntegerField(default=DialogState.AUTH)

    class Meta:
        database = db


# db.drop_tables([Items, ])
# db.create_tables([Items, ])
