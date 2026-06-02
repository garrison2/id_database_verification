#!/usr/bin/env python
import os, time
import json, csv

from util import get_most_recent_rdirs

SEARCH_RESULTS_PATH = os.getenv('SEARCH_RESULTS_PATH')
SEARCH_RESULTS_PARSED = os.getenv('SEARCH_RESULTS_PARSED')

AIRTABLE_RESULTS = os.getenv('AIRTABLE_RESULTS')
AIRTABLE_TO_JSON = os.getenv('AIRTABLE_TO_JSON')

RESULTS = os.getenv('RESULTS')
QUERIES_TO_QUESTIONS = os.getenv('QUERIES_TO_QUESTIONS')

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
                
            queries[int(query_dir)] = links
        states[state] = queries
    return states

def get_parsed(queries) -> dict():
    with open(SEARCH_RESULTS_PARSED, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        header = list(set(header[2:]))
        header.remove('TRUE')
        header.sort()

        states = { state : 
                  { i : {'links' : [], 'notes' : None } for i in range(16) }
                  for state in header }
        states_index_map = { header.index(s) : s for s in header }

        for question in range(16):
            for link in range(11):
                link_row = next(reader)[2:]
                for i in range(0, len(link_row), 2):
                    if link_row[i+1] == 'TRUE':
                        state = states_index_map[i//2]
                        if link != 10:
                            states[state][question]['links'].append(queries[state][question][link])
                        else:
                            states[state][question]['links'].append(link_row[i])

            notes = next(reader)[2:]
            for i in range(0, len(notes), 2):
                if notes[i] != '':
                    states[states_index_map[i//2]][question]['notes'] = notes[i]

            if question != 15: next(reader)

    return states

def get_airtable() -> dict():
    with open(AIRTABLE_TO_JSON, 'r') as file:
        airtable_map = json.load(file)

    states = {}
    with open(AIRTABLE_RESULTS, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)

        for row in reader:
            state = row[0]
            states[state] = {}
            for i in range(len(row[1:])):
                states[state][airtable_map[str(i)]] = row[i]

#            print(states[state])

    return states

def dump_search_results():
    results = get_parsed(get_queries_from_search())
    with open(RESULTS, 'w') as file:
        json.dump(results, file, indent=1)

def dump_airtable_results():
    results = get_airtable()
    with open(RESULTS, 'w') as file:
        json.dump(results, file, indent=1)


dump_airtable_results()
