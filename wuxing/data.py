import json
import os


FILE="records.json"


def load():
    if not os.path.exists(FILE):
        return []

    with open(FILE,"r",encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with open(FILE,"w",encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def add(name,date,time):
    data=load()

    data.append({
        "name":name,
        "date":date,
        "time":time
    })

    save(data)