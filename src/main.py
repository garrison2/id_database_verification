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

# ---------------------------------- HELPER -----------------------------------
class Args:
    def __init__(self, args):
        self.args = args[1:]
        self.original = args[1:]

    def decrement(self):
        self.args = self.args[1:]

    def check(self, num):
        if len(self.args) < num:
            raise IndexError('Expecting more arguments.')

    def get(self):
        return args.args[0]

    def __len__(self):
        return len(args.args)

def parse_state_and_query(args):
    state, query = None, None
    if len(args) < 1:
        return None, None

    if args.get() not in STATES:
        raise Exception("Argument is not a state.")

    state = args.get()
    args.decrement()

    if len(args) == 1:
        if args.get() not in QUERIES:
            raise Exception("Query is invalid.")
        query = args.get()
        args.decrement()
    elif len(args) > 1:
        raise Exception("Too many arguments.")

    args.decrement()
    return state, query

def make_state_dir(state):
        time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
        return os.path.join(RESULTS_PATH, f'{state}_{time_str}')

def get_paths(state_dir, query):
    dir_path = os.path.join(state_dir, query)
    json_path = os.path.join(dir_path, f'{query}.json')
    return dir_path, json_path

# -----------------------------------------------------------------------------

def process():
    pass

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

if __name__ == "__main__":
    args = Args(sys.argv)

    args.check(1)
    args.decrement
    match args.get():
        case 'process':
            args.check(1)
            args.decrement()

            if args.get == 'all':
                pass

            state, query = parse_state_and_query(args)
            process()
        case 'search':
            args.check(1)
            args.decrement()

            if args.get == 'all': search_all()

            state, query = parse_state_and_query(args)
            if state is None: 
                raise Exception("No state selected.")

            if query:
                search_wrapper(state, query)
            else:
                path = make_state_dir(state)

                for query in QUERIES:
                    print(type(query))
                    search_wrapper(state, query, path)
        case _:
            print("Invalid input.")

    if LOGGING:
        with open(LOGGING, 'a') as file:
            time_str = time.strftime("%d-%m-%Y_%H:%M:%S")
            text = time_str + '\t' + " ".join(sys.argv)
            file.write(text)


