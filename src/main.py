#!/usr/bin/env python
import os, sys
import json
import time
import argparse

from googleapiclient.discovery import build

API_KEY = os.getenv('CSE_KEY')
QUERIES_PATH = os.getenv('QUERIES_PATH')
STATES_PATH = os.getenv('STATES_PATH')
RESULTS_PATH = os.getenv('RESULTS_PATH')
MOBILE_ID_TERMS = os.getenv('MOBILE_ID_TERMS')
LOGGING = os.getenv('LOGGING')

with open(QUERIES_PATH, 'r') as file:
    QUERIES = json.load(file)
with open(STATES_PATH, 'r') as file:
    STATES = json.load(file)

# ---------------------------- RESULTS DIRECTORY ------------------------------
def make_rdir(state):
        time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
        return os.path.join(RESULTS_PATH, f'{state}_{time_str}')

def get_rdir_noinput(state, selection):
    directories = [ d for d in sorted(os.listdir(RESULTS_PATH)) if state in d ]
    if len(directories) == 0:
        raise Exception("State does not exist.")
    if not 0 <= int(selection) < len(directories):
        raise Exception("Invalid selection.")
    
    return directories[int(selection)]

def get_rdir_input(state):
    directories = [ d for d in sorted(os.listdir(RESULTS_PATH)) if state in d ]
    if len(directories) == 0:
        raise Exception("State does not exist.")
    if len(directories) == 1:
        return directories[0]

    print("Choose a directory:")
    for i in range(len(directories)):
        subdirs = os.listdir(os.path.join(RESULTS_PATH, directories[i]))
        print(f"\t{i} - {directories[i]} ({', '.join(subdirs)})")
    index = int(input(">> "))
    if not 0 <= index < len(directories):
        raise Exception("Invalid choice.")
    return directories[index]

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
# -----------------------------------------------------------------------------


def process(state, query, selection):
    path = os.path.join(RESULTS_PATH, selection, query, f'{query}.json')
    if not os.path.exists(path): return
    with open(path, 'r') as file:
        query_results = json.load(file)
 
def view(state, query, selection):
    path = os.path.join(RESULTS_PATH, selection, query, f'{query}.json')
    if not os.path.exists(path): return
    with open(path, 'r') as file:
        query_results = json.load(file)
    
    print(f'{selection}:')
    print(f"\t{query_results['queries']['request'][0]['searchTerms']} ({query})\n")
#    print(a['queries']['nextPage'])
    if 'items' not in query_results: 
        print("No results found.")
        return

    for i in range(len(query_results['items'])):
        website = query_results['items'][i]
        print(f"{i+1} - {website['title']}")
        print('\t' + website['link'])
    print()


# ----------------------------------JSON API ----------------------------------
def search(query, key):
    service = build("customsearch", "v1", developerKey=key)

    s = service.cse().list(q=query,
                           cx="3548decfb27244f8b"
                          ).execute()
    return s

def search_wrapper(state, query, state_dir = None):
    statute, dmv_website = STATES[state]
    query_text = QUERIES[query].format(STATE=state,
                                       STATE_STATUTE=statute, 
                                       DMV_WEBSITE=dmv_website)
    if not state_dir:
        state_dir = make_rdir(state)

    qdir_path = os.path.join(state_dir, query)
    qjson_path = os.path.join(qdir_path, f'{query}.json')

    os.makedirs(qdir_path)

    result = search(query_text, API_KEY)
    with open(qjson_path, 'w') as f:
        json.dump(result, f, indent=1)
# -----------------------------------------------------------------------------


# ----------------------------------- CLI -------------------------------------
def verify_state_and_query(state, queries):
    if state != 'all' and state not in STATES:
        raise Exception("Argument is not a state.")
    if not queries: return
    for query in queries:
        if query not in QUERIES:
            raise Exception("Query is invalid.")

def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--queries', nargs = '*',
                        help='choose specific queries (default all).')
    select = parser.add_mutually_exclusive_group()
    select.add_argument('-s', '--select',
                        help='choose the result directory to process.')
    select.add_argument('--most-recent', action='store_true',
                        help='only choose the most recent result directories.')
#    parser.add_argument('-d', '--date',
#                        help='choose a date cutoff for result directories.')
    parser.add_argument('action', choices=('process', 'view',
                                           'search', 'list'),
                        metavar="<process, view, search, list>",
                        help='choose an action.')
    parser.add_argument('state',
                        metavar='<state>',
                        help='choose a state (or "all").')
    parsed = parser.parse_args(args)

    match parsed.action:
        case 'process' | 'view':
            func = process if parsed.action == 'process' else view

            verify_state_and_query(parsed.state, parsed.queries)
            if parsed.state == 'all':
                if parsed.select:
                    raise Exception('Cannot select result directory if "all" is chosen.')
                if parsed.most_recent:
                    result_directories = get_most_recent_rdirs()
                else:
                    result_directories = os.listdir(RESULTS_PATH)

                for rdir in result_directories:
                    state = rdir[:rdir.find('_')]
                    if state not in STATES: continue
                    if parsed.queries:
                        queries = parsed.queries
                    else:
                        queries = QUERIES

                    for query in queries:
                        func(state, query, rdir)
                return

            if parsed.most_recent:
                rdir = [r for r in get_most_recent_rdirs()
                        if parsed.state in r][0]
            elif parsed.select:
                rdir = get_rdir_noinput(parsed.state, parsed.select)
            else:
                rdir = get_rdir_input(parsed.state)

            if parsed.queries:
                queries = parsed.queries
            else:
                queries = QUERIES

            for query in queries:
                func(parsed.state, query, rdir)

        case 'search':
            verify_state_and_query(parsed.state, parsed.queries)

            if parsed.queries:
                queries = parsed.queries
            else:
                queries = QUERIES

            if parsed.state == 'all':
                i = input('Are you sure? ')
                if i != 'y' and i != 'Y':
                    return

                for state in STATES:
                    rdir = make_rdir(state)

                    for query in queries:
                        search_wrapper(state, query, rdir)

            else:
                rdir = make_rdir(parsed.state)
                for query in queries:
                    search_wrapper(parsed.state, query, rdir)

        case 'list':
            verify_state_and_query(parsed.state, parsed.queries)
            if parsed.state == 'all': 
                state_count = dict()
                rdirs_sequence = dict() 

                sorted_rdirs = sorted(os.listdir(RESULTS_PATH))
                for rdir in sorted_rdirs:
                    state = rdir[:rdir.find("_")]
                    state_count[state] = state_count.get(state, -1) + 1
                    rdirs_sequence[rdir] = state_count[state]

                if parsed.most_recent:
                    result_directories = get_most_recent_rdirs()
                else:
                    result_directories = sorted_rdirs

                print('Results:')
                for rdir in result_directories:
                    sequence = rdirs_sequence[rdir]
                    queries = os.listdir(os.path.join(RESULTS_PATH, rdir))
                    print(f'\t{sequence} - {rdir} ({", ".join(queries)})')
            else:
                if parsed.most_recent:
                    result_directories = [r for r in get_most_recent_rdirs()
                                          if state in r]
                elif parsed.select:
                    result_directories = [ get_rdir_noinput(parsed.state, parsed.select) ]
                else:
                    result_directories = [os.path.join(RESULTS_PATH, r)
                                          for r in os.listdir(RESULTS_PATH) 
                                          if parsed.state in r]
                for rdir in result_directories:
                    queries = os.listdir(rdir)

                    if not parsed.queries:
                        print(f'Queries: ({rdir})')
                        for q in queries:
                            print('\t' + q)
                    else:
                        for query in parsed.queries:
                            if query not in queries:
                                raise Exception("Query is invalid.")
                        
                            files = os.listdir(os.path.join(RESULTS_PATH, rdir,
                                                            query))
                            print(f'Files: ({rdir}/{query})')
                            for f in files:
                                print('\t' + f)

    if LOGGING:
        with open(LOGGING, 'a') as file:
            time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
            text = '\n' + time_str + '\t' + " ".join(sys.argv)
            file.write(text)

if __name__ == "__main__":
    main(sys.argv[1:])
# -----------------------------------------------------------------------------
