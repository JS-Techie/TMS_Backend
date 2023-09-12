import os,inspect

def log(key : str, value : str):
    if os.getenv("print") == "true":
        print(key ," : ",value)