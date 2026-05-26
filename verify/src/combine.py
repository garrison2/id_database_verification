#!/usr/bin/env python
import os, time
import json, csv

from util import get_most_recent_rdirs
SEARCH_RESULTS_PATH = os.getenv('SEARCH_RESULTS_PATH')
CSV_RESULTS = os.getenv('CSV_RESULTS')

def get_queries_from_search() -> dict():
    states = dict()
    rdirs = get_most_recent_rdirs(SEARCH_RESULTS_PATH)
    for rdir in rdirs:
        state = rdir[:rdir.find('_')]
        rdir = os.path.join(SEARCH_RESULTS_PATH, rdir)

        queries = dict()
        for query_dir in os.listdir(rdir):
            query_json = os.path.join(rdir, query_dir, f'{query_dir}.json')
            if not os.path.exists(query_json): continue

            with open(query_json, 'r') as file:
                query_results = json.load(file)
            if 'items' not in query_results: continue

            links = []
            for website in query_results['items']:
                links.append(website['link'])
                
            queries[query_dir] = links
        states[state] = queries
    return states

results = get_queries_from_search()
print(results)

