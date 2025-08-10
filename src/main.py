#!/usr/bin/env python
import os, sys
import json
import time

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

# -------------------------------- FILESYSTEM ---------------------------------
def make_state_dir(state):
        time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
        return os.path.join(RESULTS_PATH, f'{state}_{time_str}')

def get_paths(state_dir, query):
    dir_path = os.path.join(state_dir, query)
    json_path = os.path.join(dir_path, f'{query}.json')
    return dir_path, json_path

def choose_timestamp(state):
    directories = os.listdir(RESULTS_PATH)
    directories = [ d for d in directories if state in d ]
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
# -----------------------------------------------------------------------------

def process(state, query, selection):
    path = os.path.join(RESULTS_PATH, selection, query, f'{query}.json')
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
    for i in range(len(query_results['items'])):
        website = query_results['items'][i]
        print(f"{i+1} - {website['title']}")
        print('\t' + website['link'])
    print()

def search_all():
    i = input('Are you sure? ')
    if i != 'y' and i != 'Y':
        return

    for state in STATES:
        path = make_state_dir(state)

        for query in QUERIES:
            search_wrapper(state, query, path)


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
        state_dir = make_state_dir(state)
    dir_path, json_path = get_paths(state_dir, query)
    os.makedirs(dir_path)

    result = search(query_text, API_KEY)
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=1)
# -----------------------------------------------------------------------------


# ----------------------------------- CLI -------------------------------------
def next_except(args):
    try:
        return next(args)
    except StopIteration:
        return None

def parse_state_and_query(args):
    state = next_except(args)

    if state is None:
        raise Exception("No state selected.")
    elif state != 'all' and state not in STATES:
        raise Exception("Argument is not a state.")

    query = next_except(args)
    if query and query not in QUERIES:
        raise Exception("Query is invalid.")

    if next_except(args) or (state == 'all' and query is not None):
        raise Exception("Too many arguments.")

    return state, query

def main(args):
    arg = next_except(args)
    if arg is None:
        raise Exception("Too few arguments.")

    match arg:
        case 'process' | 'view':
            func = process if arg == 'process' else view

            state, query = parse_state_and_query(args)
            if state == 'all':
                for path in os.listdir(RESULTS_PATH):
                    state = path.split('_')[0]
                    if state not in STATES: continue
                    for query in QUERIES:
                        func(state, query, path)
                return

            selection = choose_timestamp(state)
            if query:
                func(state, query, selection)
            else:
                for query in QUERIES:
                    func(state, query, selection)

        case 'search':
            state, query = parse_state_and_query(args)
            if state == 'all': search_all()
            elif query:
                search_wrapper(state, query)
            else:
                path = make_state_dir(state)

                for query in QUERIES:
                    search_wrapper(state, query, path)

        case 'list':
            state, query = parse_state_and_query(args)
            if state == 'all': 
                print('Results:')
                for p in os.listdir(RESULTS_PATH):
                    queries = os.listdir(os.path.join(RESULTS_PATH, p))
                    print(f'\t{p} ({", ".join(queries)})')
            else:
                states_dirs = [os.path.join(RESULTS_PATH, d)
                               for d in os.listdir(RESULTS_PATH) 
                               if state in d]
                for state_dir in states_dirs:
                    queries = os.listdir(state_dir)

                    if not query:
                        print(f'Queries: ({state_dir})')
                        for q in queries:
                            print('\t' + q)
                    else:
                        if query not in queries:
                            raise Exception("Query is invalid.")
                        
                        files = os.listdir(os.path.join(RESULTS_PATH, state_dir,
                                                        query))
                        print(f'Files: ({state_dir}/{query})')
                        for f in files:
                            print('\t' + f)

        case 'help':
            print("process {state/all} [query]\n"
                  "view {state/all} [query]\n"
                  "search {state/all} [query]")
        case _:
            print("Invalid input.")

    if LOGGING:
        with open(LOGGING, 'a') as file:
            time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
            text = '\n' + time_str + '\t' + " ".join(sys.argv)
            file.write(text)

if __name__ == "__main__":
    main(iter(sys.argv[1:]))
# -----------------------------------------------------------------------------
