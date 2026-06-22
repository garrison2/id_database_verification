#!/usr/bin/env python
import json

from constants import *

def get_has_digital():
    with open(AIRTABLE_RESULTS_JSON, 'r') as file:
        airtable_results = json.load(file)

    with open(SEARCH_RESULTS_JSON, 'r') as file:
        search_results = json.load(file)

    states = airtable_results.keys() | search_results.keys()
    states = { s for s in states if '_' not in s }

    for state in sorted(states):
        airtable_digital = airtable_results.get(state, dict()).get('Digital?', 'No Digital Offering') != 'No Digital Offering'
        search_digital = search_results[state]['0']['links'] +  search_results[state]['7']['links']
        
        if airtable_digital and search_digital:
            print(f'{state} (Both) - {airtable_results[state]['Digital?']}; {search_digital}')
        elif airtable_digital and not search_digital:
            print(f'{state} (Airtable) - {airtable_results[state]['Digital?']}')
        elif search_digital:
            print(f'{state} (Search) - {search_digital}')

def get_app():


get_has_digital()
