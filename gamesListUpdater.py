import json
import os
import os.path
import requests
import time
from datetime import datetime
from os import path

api_key = os.environ["API_KEY"]

with open("index.json") as json_file:
    index_data = json.load(json_file)
games_data = {}

latest_game_date = index_data["latest_game_date"]
latest_game_date_obj = datetime.fromisoformat(latest_game_date)
offset = 0
max_entries_per_index = 100
max_changes = 10

def call_api():
    response = json.loads(requests.get("https://www.giantbomb.com/api/games/?api_key=" + api_key +"&format=json&field_list=id,name,date_last_updated&filter=date_last_updated:" + latest_game_date +"|2100-01-01 00:00:00&sort=id:asc&offset=" + str(offset)).text)
    if response["status_code"] != 1: exit(1)
    offset = offset + response["number_of_page_results"]
    return response

def pick_index(id):
    if id > index_data["highest_id"]:
        count = id - index_data["highest_index"]
        remainder = max_entries_per_index - count
        if remainder > 0:
            return index_data["highest_index"]
    else
        best_match = 0
        for i in index_data["indexes"]:
            if i > best_match and i <= id:
                best_match = i
        return best_match
    return id

def load_game_data(index):
    if index not in games_data:
        if path.exists("games" + index + ".json"):
            with open("games" + index + ".json") as json_file:
                games_data[index] = json.load(json_file)
        else
            games_data[index] = []
            update_index(index)

def update_index(index):
    if index not in index_data["indexes"]:
        index_data["indexes"].append(index)
        print("Added index: " + str(index))
    if index > index_data["highest_index"]:
        index_data["highest_index"] = index

def update_games(index, data):
    load_game_data(index)
    found = 0
    for i in range(len(games_data[index])):
        if games_data[index][i]["id"] == data["id"]:
            found = 1
            games_data[index][i] = data;
    if found == 0:
        games_data[index].append(data)
        print("Added game: " + data)
    if data["id"] > index_data["highest_id"]:
        index_data["highest_id"] = data["id"]
    game_update = datetime.fromisoformat(data["date_last_updated"])
    if game_update > latest_game_date_obj:
        latest_game_date_obj = game_update
        index_data["latest_game_date"] = data["date_last_updated"]

response = call_api()
while response["number_of_page_results"] > 0:
    for x in response["results"]:
        index = pick_index(x["id"])
        update_games(index, x)
    time.sleep(1)
    response = call_api()

if len(games_data) > 0:
    index_data["version"] = index_data["version"] + 1
    while len(index_data["index_changes"]) >= max_changes:
        highest = 0
        for k in index_data["index_changes"]:
            if k > highest:
                highest = k
        if highest > 0:
            del index_data["index_changes"][highest]
    index_data["index_changes"][index_data["version"]] = []
    for k in games_data:
        index_data["index_changes"][index_data["version"]].append(k)

with open("index.json", "w") as json_file:
    json.dump(index_data, json_file)

for k in games_data:
    with open("games" + k + ".json", "w") as json_file:
        json.dump(games_data[k], json_file)