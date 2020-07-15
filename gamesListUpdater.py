import json
import os
import os.path
import pprint
import requests
import time
from datetime import datetime
from os import path

start_time = time.time()

api_key = os.environ.get("API_KEY", "")
debugon = int(os.environ.get("DEBUGON", "0"))

if debugon == 1:
    print("Debug on")
    print("API Key: " + api_key)

if len(api_key) == 0:
    print("API Key missing, aborting...")
    exit(1)

with open("index.json") as json_file:
    index_data = json.load(json_file)
games_data = {}

latest_game_date = index_data["latest_game_date"]
latest_game_date_obj = datetime.fromisoformat(latest_game_date)
offset = 0
max_entries_per_index = 100
max_changes = 10
changed = 0

if debugon == 1:
    print("  latest_game_date: " + latest_game_date)

def call_api():
    global offset
    global api_key
    global latest_game_date
    url = "https://www.giantbomb.com/api/games/"
    query = {"api_key": api_key, "format": "json", "field_list": "id,name,date_last_updated", "filter": "date_last_updated:" + latest_game_date +"|2100-01-01 00:00:00", "sort": "id:asc", "offset": str(offset)}
    if debugon == 1:
        print("    Performing API call")
    resp = requests.get(url, params=query, headers={ "User-Agent": "PhantomBot.gamesListUpdater/2020" })
    if debugon == 1:
        print("    API Response")
        print("     " + str(resp.status_code))
        print("     " + resp.reason)
        for k, v in resp.headers.items():
            print("     [" + k + "] " + v)
        print("     " + resp.text)
    if resp.status_code != 200:
        if debugon == 1:
            print("    Unsatisfactory status code(" + str(resp.status_code) + "), aborting...")
        exit(1)
    response = json.loads(resp.text)
    if debugon == 1:
        print("    Completed API call")
    if response["status_code"] != 1:
        if debugon == 1:
            print("    Unsatisfactory status code(" + str(response["status_code"]) + "), aborting...")
        exit(1)
    offset = offset + response["number_of_page_results"]
    if debugon == 1:
        print("    Next offset: " + str(offset))
    return response

def pick_index(id):
    global index_data
    global max_entries_per_index
    if id > index_data["highest_id"]:
        count = id - index_data["highest_index"]
        remainder = max_entries_per_index - count
        if remainder > 0:
            return index_data["highest_index"]
    else:
        best_match = 0
        for i in index_data["indexes"]:
            if i > best_match and i <= id:
                best_match = i
        return best_match
    return id

def load_game_data(index):
    global games_data
    if index not in games_data:
        if path.exists("data/games" + str(index) + ".json"):
            with open("data/games" + str(index) + ".json") as json_file:
                if debugon == 1:
                    print("        Loaded game data file: games" + str(index) + ".json")
                games_data[index] = json.load(json_file)
        else:
            if debugon == 1:
                print("        Creating new game data file: games" + str(index) + ".json")
            games_data[index] = []
            update_index(index)

def update_index(index):
    global index_data
    global changed
    if index not in index_data["indexes"]:
        index_data["indexes"].append(index)
        changed = 1
        print("Added index: " + str(index))
    if index > index_data["highest_index"]:
        index_data["highest_index"] = index
        if debugon == 1:
            print("          New highest index: " + str(index_data["highest_index"]))

def update_games(index, data):
    global index_data
    global games_data
    global latest_game_date_obj
    global changed
    load_game_data(index)
    found = 0
    for i in range(len(games_data[index])):
        if games_data[index][i]["id"] == data["id"]:
            found = 1
            if games_data[index][i]["name"] != data["name"]:
                changed = 1
            games_data[index][i] = data;
            if debugon == 1:
                print("      Updated existing game")
    if found == 0:
        games_data[index].append(data)
        changed = 1
        print("Added game: " + str(data["id"]) + " -> " + data["name"])
    if data["id"] > index_data["highest_id"]:
        index_data["highest_id"] = data["id"]
        if debugon == 1:
            print("      New highest id: " + str(index_data["highest_id"]))
    game_update = datetime.fromisoformat(data["date_last_updated"])
    if game_update > latest_game_date_obj:
        latest_game_date_obj = game_update
        index_data["latest_game_date"] = data["date_last_updated"]
        if debugon == 1:
            print("      New highest date: " + index_data["latest_game_date"])

response = call_api()
while response["number_of_page_results"] > 0:
    for x in response["results"]:
        index = pick_index(x["id"])
        if debugon == 1:
            print("  Using index: " + str(index))
        update_games(index, x)
    time.sleep(1)
    response = call_api()

if changed == 1:
    index_data["version"] = index_data["version"] + 1
    if debugon == 1:
        print("  Publishing new version: " + str(index_data["version"]))
    while len(index_data["index_changes"]) >= max_changes:
        highest = 0
        for k in index_data["index_changes"]:
            if k > highest:
                highest = k
        if highest > 0:
            if debugon == 1:
                print("  Removing old patch index")
                pp = pprint.PrettyPrinter(indent=3)
                pp.pprint(index_data["index_changes"][highest])
            del index_data["index_changes"][highest]
    index_data["index_changes"][index_data["version"]] = []
    for k in games_data:
        index_data["index_changes"][index_data["version"]].append(k)

with open("index.json", "w") as json_file:
    json.dump(index_data, json_file)
    if debugon == 1:
        print("Wrote new index.json")

for k in games_data:
    with open("data/games" + str(k) + ".json", "w") as json_file:
        json.dump(games_data[k], json_file)
        if debugon == 1:
            print("Wrote new games" + str(k) + ".json")

print("Finished in %s seconds" % (time.time() - start_time))
