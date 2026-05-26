#!/usr/bin/env python
import os, time
import json, csv

RESULTS_PATH = os.getenv('RESULTS_PATH')
CSV_RESULTS = os.getenv('CSV_RESULTS')
HYPERLINK_FORMAT = '=HYPERLINK("{0}", "{1}")'

def get_most_recent_rdirs():
    convert = lambda t: time.mktime(time.strptime(t, "%d-%m-%Y_%H:%M:%S"))
    
    states = dict()
    for rdir in os.listdir(RESULTS_PATH):
        state = rdir[:rdir.find('_')]
        tval = convert(rdir[rdir.find('_') + 1:])
        if tval > states.get(state, (0, None))[0]:
            states[state] = (tval, rdir)

    results = []
    for state in states:
        results.append(states[state][1])

    results.sort()
    return results

states = dict()
rdirs = get_most_recent_rdirs()
for rdir in rdirs:
    state = rdir[:rdir.find('_')]
    rdir = os.path.join(RESULTS_PATH, rdir)

    queries = dict()
    for query_dir in os.listdir(rdir):
        query_json = os.path.join(rdir, query_dir, f'{query_dir}.json')
        if not os.path.exists(query_json): continue

        with open(query_json, 'r') as file:
            query_results = json.load(file)
        if 'items' not in query_results: continue

        links = []
        for website in query_results['items']:
            links.append(HYPERLINK_FORMAT.format(website['link'], 
                                                 website['title'].replace('"', '')))
            
        queries[query_dir] = links
    states[state] = queries

for state in states:
    print(states[state])

QUERIES_COLUMNS = False

if QUERIES_COLUMNS:
    with open(CSV_RESULTS, 'w') as file:
        writer = csv.writer(file)
        header = [ '' if i % 2 == 0 else f'Q{i//2}' for i in range(32) ]
        writer.writerow(header)
        for state in states:
            rows = [ ['' for _ in range(16) ] for __ in range(10)]
            for query in sorted(states[state].keys()):
                for i in range(len(states[state][query])):
                    link = states[state][query][i]
                    rows[i][int(query)] = link
            for i in range(len(rows)):
                row = rows[i]
                print_row = [ '' if i % 2 == 0 else row[i//2] for i in range(32) ]
                if i == 0:
                    print_row[0] = state
                writer.writerow(print_row)
            writer.writerow([])
    exit()


queries = dict()
for state in states:
    for query in states[state]:
        queries[query] = queries.get(query, dict()) | {state:states[state][query]}

with open(CSV_RESULTS, 'w') as file:
    writer = csv.writer(file)
    states = sorted(states.keys())
    header = [ '' if i % 2 == 0 else states[i//2] for i in range(102) ]
    writer.writerow(header)

    for query in sorted(queries.keys()):
        rows = [ ['' for _ in range(100) ] for __ in range(10)]
        for i in range(len(states)):
            state = states[i]
            if state not in queries[query]: continue
            for j in range(len(queries[query][state])):
                link = queries[query][state][j]
                rows[j][i] = link
        for i in range(len(rows)):
            row = rows[i]
            print_row = [ '' if i % 2 == 0 else row[i//2] for i in range(102) ]
            if i == 0:
                print_row[0] = f'Q{query}'
            writer.writerow(print_row)
        writer.writerow([])
