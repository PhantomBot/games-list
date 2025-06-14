# Copyright (C) 2016-2020 phantombot.github.io
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import pprint
import requests
import time
from datetime import datetime
from os import path

start_time = time.time()

api_key = os.environ.get("API_KEY", "")
do_deletes = int(os.environ.get("DO_DELETES", "0"))
debugon = int(os.environ.get("DEBUGON", "0"))

ratelimit = 10
ratelimit502 = 30
max502retry = 10
ratelimit420 = 300
maxratelimit420 = 1800
ratelimititerations = 20
ratelimitmultiplier = 7

nextratelimit420 = ratelimit420

if debugon == 1:
    print("Debug on", flush=True)
    print("API Key: " + api_key, flush=True)

if len(api_key) == 0:
    print("API Key missing, aborting...", flush=True)
    exit(1)

with open("index.json") as json_file:
    index_data = json.load(json_file)
games_data = {}

latest_game_date = index_data["latest_game_date"]
latest_game_date_obj = datetime.fromisoformat(latest_game_date)
offset = 0
max_entries_per_index = 100
max_changes = 10
changed = []
to_delete = []
total_entries = 0

if do_deletes == 1:
    latest_game_date = "2000-01-01 00:00:00"

if debugon == 1:
    print("  latest_game_date: " + latest_game_date, flush=True)

def call_api(retry=1):
    global offset
    global total_entries
    global nextratelimit420
    url = "https://www.giantbomb.com/api/games/"
    query = {"api_key": api_key, "format": "json", "field_list": "id,name,date_last_updated", "filter": "date_last_updated:" + latest_game_date +"|2100-01-01 00:00:00", "sort": "id:asc", "offset": str(offset)}
    if debugon == 1:
        print("    Performing API call", flush=True)
    else:
        print("API Call", str(offset), "/", str(total_entries), "...", end="", flush=True)
    resp = requests.get(url, params=query, headers={ "User-Agent": "PhantomBot.gamesListUpdater/2020" })
    if debugon == 1:
        print("    API Response", flush=True)
        print("     " + str(resp.status_code), flush=True)
        print("     " + resp.reason, flush=True)
        for k, v in resp.headers.items():
            print("     [" + k + "] " + v, flush=True)
        print("     " + resp.text, flush=True)
    else:
        print(str(resp.status_code), resp.reason, end="", flush=True)
    if resp.status_code != 200:
        if (resp.status_code == 502 or resp.status_code == 503) and retry <= max502retry:
            print(flush=True)
            time.sleep(ratelimit502 * retry)
            return call_api(retry=retry + 1)
        if resp.status_code == 420 and nextratelimit420 <= maxratelimit420:
            print(flush=True)
            print("Rate limiting (" + str(nextratelimit420) + ")...", end="", flush=True)
            time.sleep(nextratelimit420)
            print("Done", flush=True)
            nextratelimit420 = nextratelimit420 + ratelimit420
            return call_api()
        if debugon == 1:
            print("    Unsatisfactory status code(" + str(resp.status_code) + "), aborting...", flush=True)
        else:
            print(flush=True)
        exit(1)
    nextratelimit420 = ratelimit420
    response = json.loads(resp.text)
    if debugon == 1:
        print("    Completed API call", flush=True)
    else:
        print("", response["status_code"], response["error"], end="", flush=True)
    if response["status_code"] != 1:
        if debugon == 1:
            print("    Unsatisfactory status code(" + str(response["status_code"]) + "), aborting...", flush=True)
        else:
            print(flush=True)
        exit(1)
    offset = offset + response["number_of_page_results"]
    total_entries = response["number_of_total_results"]
    if debugon == 1:
        print("    Next offset: " + str(offset), flush=True)
    else:
        print("\r", end="", flush=True)
    return response

def pick_index(idx):
    global index_data
    global max_entries_per_index
    if idx > index_data["highest_id"]:
        count = idx - index_data["highest_index"]
        remainder = max_entries_per_index - count
        if remainder > 0:
            return index_data["highest_index"]
    else:
        best_match = 0
        for i in index_data["indexes"]:
            if i > best_match and i <= idx:
                best_match = i
        return best_match
    return idx

def load_game_data(index):
    global games_data
    if index not in games_data:
        if path.exists("data/games" + str(index) + ".json"):
            with open("data/games" + str(index) + ".json") as json_file:
                if debugon == 1:
                    print("        Loaded game data file: games" + str(index) + ".json", flush=True)
                games_data[index] = json.load(json_file)
        else:
            if debugon == 1:
                print("        Creating new game data file: games" + str(index) + ".json", flush=True)
            games_data[index] = []
            update_index(index)

def update_index(index):
    global index_data
    global changed
    if index not in index_data["indexes"]:
        index_data["indexes"].append(index)
        if index not in changed:
            changed.append(index)
        print("Added index: " + str(index), flush=True)
    if index > index_data["highest_index"]:
        index_data["highest_index"] = index
        if debugon == 1:
            print("          New highest index: " + str(index_data["highest_index"]), flush=True)

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
            old_names = []
            if games_data[index][i]["name"] != data["name"]:
                if index not in changed:
                    changed.append(index)
                if "old_names" in games_data[index][i]:
                    old_names = games_data[index][i]["old_names"]
                if games_data[index][i]["name"] not in old_names:
                    old_names.append(games_data[index][i]["name"])
            games_data[index][i] = data;
            games_data[index][i]["old_names"] = old_names
            if debugon == 1:
                print("      Updated existing game", flush=True)
            if do_deletes == 1 and data["id"] in to_delete:
                to_delete.remove(data["id"])
            break
    if found == 0:
        games_data[index].append(data)
        if index not in changed:
            changed.append(index)
        print("Added game: " + str(data["id"]) + " -> " + data["name"], flush=True)
    if data["id"] > index_data["highest_id"]:
        index_data["highest_id"] = data["id"]
        if debugon == 1:
            print("      New highest id: " + str(index_data["highest_id"]), flush=True)
    game_update = datetime.fromisoformat(data["date_last_updated"])
    if game_update > latest_game_date_obj:
        latest_game_date_obj = game_update
        index_data["latest_game_date"] = data["date_last_updated"]
        if debugon == 1:
            print("      New highest date: " + index_data["latest_game_date"], flush=True)

if do_deletes == 1:
    for i in index_data["indexes"]:
        load_game_data(i)
    for k in games_data:
        for i in range(len(games_data[k])):
            to_delete.append(games_data[k][i]["id"])

response = call_api()
iteration = 0
while response["number_of_page_results"] > 0:
    for x in response["results"]:
        index = pick_index(x["id"])
        if debugon == 1:
            print("  Using index: " + str(index), flush=True)
        update_games(index, x)
    time.sleep(ratelimit)
    iteration = iteration + 1
    if iteration >= ratelimititerations:
        print("Rate limiting...", end="", flush=True)
        time.sleep(ratelimit * ratelimitmultiplier)
        print("Done", flush=True)
        iteration = 0
    response = call_api()

print(flush=True)

if len(changed) > 0 or len(to_delete) > 0:
    index_data["version"] = index_data["version"] + 1
    if debugon == 1:
        print("  Publishing new version: " + str(index_data["version"]), flush=True)
    while len(index_data["index_changes"]) >= max_changes:
        lowest = 0
        for k in index_data["index_changes"]:
            if int(k) < lowest or lowest == 0:
                lowest = int(k)
        if lowest > 0:
            if debugon == 1:
                print("  Removing old patch index", flush=True)
                pp = pprint.PrettyPrinter(indent=3)
                pp.pprint(index_data["index_changes"][lowest])
            del index_data["index_changes"][str(lowest)]
            if lowest in index_data["deletes"]:
                del index_data["deletes"][str(lowest)]
    index_data["index_changes"][index_data["version"]] = []
    if do_deletes == 1:
        index_data["deletes"][index_data["version"]] = []
        for x in to_delete:
            index = pick_index(x)
            for i in range(len(games_data[index])):
                if games_data[index][i]["id"] == x:
                    print("Deleted game: " + str(games_data[index][i]["id"]) + " -> " + games_data[index][i]["name"], flush=True)
                    index_data["deletes"][index_data["version"]].append(games_data[index][i]["name"])
                    del games_data[index][i]
                    changed.append(index)
                    break
    for k in changed:
        index_data["index_changes"][index_data["version"]].append(k)

with open("index.json", "w") as json_file:
    json.dump(index_data, json_file)
    if debugon == 1:
        print("Wrote new index.json", flush=True)

for k in games_data:
    with open("data/games" + str(k) + ".json", "w") as json_file:
        json.dump(games_data[k], json_file)
        if debugon == 1:
            print("Wrote new games" + str(k) + ".json", flush=True)

print("Finished in %s seconds" % (time.time() - start_time), flush=True)
