from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase, ArrayField
from enum import Enum
from config import bdname, bduser, bdpassword, bdport, bdhost

db = PostgresqlExtDatabase(bdname, user=bduser, password=bdpassword,
                           host=bdhost, port=bdport)


class TaskStatus:
    FOR_UPDATE = 0
    FOR_LOAD = 1
    LOAD_COMPLE = 2
    UPDATE_COMPLE = 3


class DialogState:
    MENU = 0
    WAIT_WILBERRIES_FOR_LOAD = 1
    WAIT_WILBERRIES_FOR_PARSE = 2
    WAIT_OZON_FOR_LOAD = 3
    WAIT_OZON_FOR_PARSE = 4
    WAIT_BERU_FOR_LOAD = 5
    WAIT_BERU_FOR_PARSE = 6


class Items(Model):
    url = TextField()
    stars = TextField(default="")
    price = IntegerField(default=0)
    review = IntegerField(default=0)
    stock = IntegerField(default=0)
    sold = IntegerField(default=0)
    status = IntegerField()
    shop = TextField()
    brand = TextField(default="-")
    color = TextField(default="-")

    class Meta:
        database = db


class Users(Model):
    tel_id = BigIntegerField(unique=True)
    name = TextField()
    dstat = IntegerField(default=0)

    class Meta:
        database = db


# db.drop_tables([Items, Users])
# db.create_tables([Items, Users])
