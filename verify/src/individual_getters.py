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

def get_urls():
    with open(COMBINED_RESULTS, 'r') as file:
        combined_results = json.load(file)

    with open(SELECTED_STATES, 'r') as file:
        selected_states = json.load(file)

    for state in selected_states:
        state_list = []
        for category in combined_results[state]:
            if category == 'notes': continue
            for subcategory in combined_results[state][category]:
                value = combined_results[state][category][subcategory].get('value', [])
                if (isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict)):
                    value = [s for val in value if 'source' in val for s in val['source']]
                else:
                    value = []

                google_source = combined_results[state][category][subcategory].get('GoogleSource', [])
                airtable_source = combined_results[state][category][subcategory].get('AirtableSource', [])
                airtable_source = [s for val in airtable_source if 'source' in val for s in val['source']]
                state_list += value + airtable_source + google_source

        state_list = list(set(state_list))
        with open(f'results/state_links/{state}', 'w') as file:
            for link in state_list:
                file.write(f'{link}\n')

# get_has_digital()
get_urls()
