import os
import datetime


def log(key: str, value: str | None = None):
    if os.getenv("print") == "true":
        print(key, " : ", value)


def convert_date_to_string(date: datetime.datetime):

    return (str(date.year)+"-"+str(date.month)+"-"+str(date.hour)+" "+str(date.hour)+":"+str(date.minute))
