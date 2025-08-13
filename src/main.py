#!/usr/bin/env python
import os, sys
import json
import time
import argparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

API_KEY = os.getenv('CSE_KEY')
LOGGING = os.getenv('LOGGING')
MOBILE_ID_TERMS = os.getenv('MOBILE_ID_TERMS')
SEARCHLIST_PATH = os.getenv('SEARCHLIST')

if os.getenv("USE_TMP"):
    QUERIES_PATH = os.getenv('TMP_QUERIES_PATH') or os.getenv('QUERIES_PATH')
    STATES_PATH = os.getenv('TMP_STATES_PATH') or os.getenv('STATES_PATH')
    RESULTS_PATH = os.getenv('TMP_RESULTS_PATH') or os.getenv('RESULTS_PATH')
else:
    QUERIES_PATH = os.getenv('QUERIES_PATH')
    STATES_PATH = os.getenv('STATES_PATH')
    RESULTS_PATH = os.getenv('RESULTS_PATH')


with open(QUERIES_PATH, 'r') as file:
    QUERIES = json.load(file)

with open(STATES_PATH, 'r') as file:
    STATES = json.load(file)

with open(SEARCHLIST_PATH, 'r') as file:
    SEARCHLIST = [s.strip() for s in file.readlines()]

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

def get_rdirs(state, single=False, select=None, most_recent=None, time=None):
    if state == 'all':
        if select:
            raise Exception('Cannot select result directory if "all" is chosen.')
        elif most_recent:
            rdirs = get_most_recent_rdirs()
        else:
            rdirs = os.listdir(RESULTS_PATH)
        if time:
            rdirs = [ r for r in rdirs if time in r ]

        return rdirs

    if most_recent:
        rdirs = [ r for r in get_most_recent_rdirs() if state in r ]
    elif select:
        rdirs = [ get_rdir_noinput(state, select) ]
    else:
        if single:
            rdirs = [ get_rdir_input(state) ]
        else:
            rdirs = [os.path.join(RESULTS_PATH, r)
                     for r in os.listdir(RESULTS_PATH) 
                     if state in r]

    if time:
        rdirs = [ r for r in rdirs if time in r ]


    if single:
        return rdirs[0] if rdirs else ''
    return rdirs
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
    attempt = 0
    while True:
        try:
            service = build("customsearch", "v1", developerKey=key)

            s = service.cse().list(q=query,
                                   cx="3548decfb27244f8b"
                                  ).execute()
            return s

        except HttpError as e:
            sleep_time = 45 * 2 ** attempt
            print(f'Sleeping {sleep_time} seconds. (attempt {attempt})')
            time.sleep(sleep_time)

            if LOGGING:
                with open(LOGGING, 'a') as file:
                    time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
                    text = f'\n{time_str}query={query}\tattempt={attempt}\tsleep_time={sleep_time}'
                    file.write(text)
            attempt += 1

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
    parser.add_argument('-t', '--time',
                        help=('choose a time results directories must be from, '
                              'in format: dd-mm-yyyy_hh:mm:ss.')
                        )
    parser.add_argument('--confirm', metavar="i", type=int,
                        help=('prompt a confirmation every i searches '
                              'when searching "all".'))
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
                result_directories = get_rdirs('all', False, parsed.select, 
                                               parsed.most_recent, parsed.time)

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

            rdir = get_rdirs(parsed.state, True, parsed.select, 
                             parsed.most_recent, parsed.time)
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
                def proceed():
                    prompt = input('Proceed? ')
                    if prompt != 'y' and prompt != 'Y':
                        exit()
                proceed()

                confirm = int(parsed.confirm) if parsed.confirm else None

                i = 0
                for state in STATES:
                    if state not in SEARCHLIST: continue
                    print(state)
                    if confirm and i % confirm == 0:
                        print(f'{i} states searched.')
                        proceed()
                    rdir = make_rdir(state)

                    for query in queries:
                        search_wrapper(state, query, rdir)
                    i += 1

            else:
                rdir = make_rdir(parsed.state)
                for query in queries:
                    search_wrapper(parsed.state, query, rdir)

        case 'list':
            verify_state_and_query(parsed.state, parsed.queries)
            if parsed.state == 'all': 
                state_count = dict()
                rdirs_sequence = dict() 

                for rdir in sorted(os.listdir(RESULTS_PATH)):
                    state = rdir[:rdir.find("_")]
                    state_count[state] = state_count.get(state, -1) + 1
                    rdirs_sequence[rdir] = state_count[state]

                result_directories = get_rdirs('all', False, parsed.select, 
                                               parsed.most_recent, parsed.time)


                print('Results:')
                for rdir in result_directories:
                    sequence = rdirs_sequence[rdir]
                    queries = os.listdir(os.path.join(RESULTS_PATH, rdir))
                    print(f'\t{sequence} - {rdir} ({", ".join(queries)})')
            else:
                result_directories = get_rdirs(parsed.state, False, parsed.select, 
                                               parsed.most_recent, parsed.time)

                for rdir in result_directories:
                    queries = os.listdir(os.path.join(RESULTS_PATH, rdir))

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
