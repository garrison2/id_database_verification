#!/usr/bin/env python
import os, sys
import json, csv, re

QUERIES_PATH = os.getenv('QUERIES_PATH')
STATES_PATH = os.getenv('STATES_PATH')
QUERIES_CONVERT = os.getenv('QUERIES_CONVERT')
STATES_CONVERT = os.getenv('STATES_CONVERT')

def clean(text):
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    return text

def query_to_string(query):
    if query < 10: return f'0{query}'
    else: return str(query)

def parse_queries():
    queries = []
    terms = dict()
    environment = None

    with open(QUERIES_CONVERT, 'r') as file:
        for line in file:
            line = line.strip()
            if line == '': continue

            match line:
                case '# queries':
                    environment = 'queries'
                case '# terms':
                    environment = 'terms'
                case _:
                    if environment == 'terms':
                        delim = line.find(': ')
                        term = line[:delim]
                        definition = line[delim+2:]
                        terms[term] = definition
                    else:
                        queries.append(clean(line.format(**terms)))

    queries_dict = dict()
    for i in range(len(queries)):
        index = query_to_string(i)
        queries_dict[index] = queries[i]

    with open(QUERIES_PATH, 'w') as file:
        json.dump(queries_dict, file, indent=1)

def parse_states():
    states = dict()
    with open(STATES_CONVERT, 'r') as file:
        reader = csv.reader(file)

        next(reader)
        for line in reader:
            state, statute, dmv = line
            states[state] = [statute, dmv]

    with open(STATES_PATH, 'w') as file:
        json.dump(states, file, indent=1)

def main():
    parse_queries()
    parse_states()

    pass

if __name__ == '__main__':
    match len(sys.argv):
        case 1:
            main()
        case 2:
            if sys.argv[1] == 'queries':
                parse_queries()
            elif sys.argv[1] == 'states':
                parse_states()
            else:
                print(f'Invalid argument "{sys.argv[1]}".')
        case _:
            print(f"Invalid number of arguments: Expected 1 or 2. Received {_}.")
