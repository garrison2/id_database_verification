#!/usr/bin/env python
import pprint
import os
import sys
import json

import time

from googleapiclient.discovery import build

ROOT = os.path.join(os.path.dirname(__file__), "..")
QUERIES_PATH = os.path.join(ROOT, 'queries.json')
RESULTS_PATH = os.path.join(ROOT, "results")
API_KEY = os.getenv('CSE_KEY')

def search(query, key):
    service = build("customsearch", "v1", developerKey=key)

    s = service.cse().list(q=query,
                           cx="3548decfb27244f8b"
                          ).execute()
    return s
def main():
    with open(QUERIES_PATH, 'r') as file:
        queries = json.load(file)

    for query in queries:
        result = search(query, API_KEY)
        time_str = time.strftime("%Y.%m.%d-%H:%M:%S")
        with open(os.path.join(RESULTS_PATH, f"{time_str}.json"), 'w') as f:
            json.dump(result, f, indent=1)

if __name__ == "__main__":
     main()
#    search(sys.argv[1], os.getenv('CSE_KEY'))

# "arizona revised statutes" "identification card" OR "driver license"
