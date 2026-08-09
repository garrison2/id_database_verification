#!/usr/bin/env python
import os
import json
import re
import textwrap
from enum import Enum
from dataclasses import dataclass
from urllib.parse import urlparse

from constants import *
import test_suite

import pprint

# COMBINING
TERMINAL_WIDTH = shutil.get_terminal_size().columns
TABSIZE = 8

@dataclass(frozen=True)
class Info:
    airtable_flattened: list
    airtatable_refs: list
    google_sources: list
    google_notes: str

    @staticmethod
    def flatten_info(info) -> Info:
        value = info.get('value')
        airtable_sources = info.get('AirtableSource')
        google_sources = info.get('GoogleSource', [])
        google_notes = info.get('GoogleNotes', [])

        airtable_flattened = []
        airtable_refs = []

        def add_blocks(blocks):
            for block in blocks:
                if 'title' in block:
                    airtable_flattened.append(block['title'])
                    airtable_refs.append(block)
                if 'value' in block:
                    airtable_flattened.append(block['value'])
                    airtable_refs.append(block)
                for source in block.get('source', []):
                    airtable_flattened.append(source)
                    airtable_refs.append(block)

        if isinstance(value, list):
            if isinstance(value[0], dict):
                add_blocks(value)
            else:
                airtable_flattened.append(', '.join(value))
                airtable_refs.append(value)
        elif isinstance(value, str):
            airtable_flattened.append(value)
            airtable_refs.append(value)

        if airtable_sources is not None:
            add_blocks(airtable_sources)

        return Info(airtable_flattened, 
                    airtable_refs, 
                    google_sources, 
                    '\n'.join(google_notes))

    def print(self):
        for i in range(len(self.airtable_flattened)):
            i_str = str(i) if i >= 10 else f'0{str(i)}'
            print_wrapped(f'{i_str}a - {self.airtable_flattened[i]}', 3, 6)
        print()
        for i in range(len(self.google_sources)):
            i_str = str(i) if i >= 10 else f'0{str(i)}'
            print_wrapped(f'{i_str}g - {self.google_sources[i]}', 3, 6)
        if self.google_notes:
            print()
            print_wrapped(self.google_notes, 3)

class Action(Enum):
    MERGE = 0
    EDIT = 1
    UNDO = 2
    CONTINUE = 3

class DataType(Enum):
    AIRTABLE = 0
    GOOGLE = 1

@dataclass(frozen=True)
class UserInput:
    action: Action
    number: int
    data_type: DataType

    @staticmethod
    def parse_input(input_val):
        pattern = r'^(?:([A-Za-z])?(\d)?(\d)([A-Za-z])|([A-Za-z]))$'

        if input_val is '':
            raise InputError(f'"{input_val}" is an invalid input.')

        input_parsed = re.match(pattern, input_val, re.IGNORECASE)
        if input_parsed is None:
            raise InputError(f'"{input_val}" is an invalid input.')

        action1, num1, num2, data_type, action2 = input_parsed.groups()
        if action2:
            match action2:
                case 'u' | 'U':
                    return UserInput(Action.UNDO, None, None)
                case 'c' | 'C':
                    return UserInput(Action.CONTINUE, None, None)
                case _:
                    raise InputError(f'"{action2}" is an invalid action.')

        number = int((num1 or '') + num2)
        match action1:
            case None | 'm' | 'M':
                action1 = Action.MERGE
                action1 = Action.MERGE
            case 'e' | 'E':
                action1 = Action.EDIT
            case 'u' | 'U':
                action1 = Action.UNDO
            case _:
                raise InputError(f'"{action1}" is an invalid action.')
        
        match data_type:
            case 'a' | 'A':
                data_type = DataType.AIRTABLE
            case 'g' | 'G':
                data_type = DataType.GOOGLE
            case _:
                raise InputError(f'"{data_type}" is an invalid data type.')

        return UserInput(action1, number, data_type)

class InputError(Exception):
    pass

def print_side_by_side(left: list, right: list):
    result = []

    while any(strings):
        line = []

        for i, s in enumerate(strings):
            line.append(s[:size].ljust(size))
            strings[i] = s[size:]

        result.append((" " * space).join(line))
    
    return "\n".join(result)

def combine_airtable_and_search():
    with open(QUERIES_TO_QUESTIONS, 'r') as file:
        queries_map = json.load(file)
    with open(SEARCH_RESULTS_PARSED, 'r') as file:
        search_results_parsed = json.load(file)
    with open(AIRTABLE_RESULTS_PARSED, 'r') as file:
        airtable_results_parsed = json.load(file)

    states_list = sorted(list(search_results_parsed.keys() | airtable_results_parsed.keys()))

    combined = dict()

    for state in states_list:
        combined[state] = dict()
        combined[state]['notes'] = airtable_results_parsed[state].get('Meta', dict()).get('General Notes', dict())

        for category in queries_map:
            combined[state][category] = dict()
            for subcategory in queries_map[category]:

                if (category in airtable_results_parsed[state] and
                    subcategory in airtable_results_parsed[state][category]):
                    combined[state][category][subcategory] = airtable_results_parsed[state][category][subcategory]

                if state not in search_results_parsed:
                    modified_state = state[:state.find('_')]
                else:
                    modified_state = state

                combined[state][category][subcategory] = combined[state][category].get(subcategory, dict())
                subcat = combined[state][category][subcategory]

                search_nums = queries_map[category][subcategory]

                links = [link for num in search_nums for link in search_results_parsed[modified_state][str(num)]['links']]
                notes = [search_results_parsed[modified_state][str(num)]['notes'] for num in search_nums 
                         if search_results_parsed[modified_state][str(num)]['notes']]

                # remove duplicates while retaining order
                links = list(dict.fromkeys(links))
                notes = list(dict.fromkeys(notes))

                for search_index in range(len(links)):
                    search_link = urlparse(links[search_index])
                    if 'AirtableSource' in subcat:
                        airtable_index = 1 if 'value' in subcat else 0
                        for item in subcat['AirtableSource']:
                            if 'source' in item:
                                for airtable_link in item['source']:
                                    airtable_link = urlparse(airtable_link)
                                    if search_link[0:5] == airtable_link[0:5]:
                                        links[search_index] = f'[Airtable {airtable_index}]'
                                        print(state, category, subcategory, links[search_index])
                                        break
                            airtable_index += 1

                if links:
                    subcat['GoogleSource'] = links
                if links and notes: # only add notes if links matched
                    subcat['GoogleNotes'] = notes 

    with open(COMBINED_RESULTS, 'w') as file:
        json.dump(combined, file, indent=1)

def select_from_combined():
    with open(COMBINED_RESULTS, 'r') as file:
        combined = json.load(file)
    try:
        with open(COMBINE_LOGS, 'r') as file:
            logs = json.load(file)
    except FileNotFoundError:
        logs = dict()


    logs['seen'] = logs.get('seen', dict())

    if not os.path.isdir(COMBINE_DIR):
        os.makedirs(COMBINE_DIR)

    for state in combined:
        print_wrapped(state)
        logs['seen'][state] = logs['seen'].get(state, dict())
        for category in combined[state]:
            print_wrapped(category, 1)
            logs['seen'][state][category] = logs['seen'][state].get(category, [])
            for subcategory in combined[state][category]:
                if category == 'notes':
                    print_wrapped(combined[state][category][subcategory], 2)
                    continue
                if subcategory in logs['seen'][state][category]:
                    continue

                print_wrapped(subcategory, 2)

                info = Info.flatten_info(combined[state][category][subcategory])
                info.print()
#                print_info(combined[state][category][subcategory], None, None)

                user_input = None
                while user_input is None:
                    try:
                        user_input = UserInput.parse_input(input('> '))
                    except InputError as e:
                        print(e)
                        pass

# @param tabstop1   The number of TAB-WIDTH spaces to indent the first line to
# @param tabstop2   The number of SINGLE-SPACES to FURTHER indent subsequent lines
def print_wrapped(val, tabstop1 = 0, tabstop2 = None):
    if val is None: 
        return
    if isinstance(val, bool):
        val = str(val)
    tabstop1 = f'{' ' * round(TABSIZE * tabstop1)}'
    tabstop2 = tabstop1 + f'{' ' * tabstop2}' if tabstop2 else tabstop1

    lines = textwrap.wrap(val, 
                          width = TERMINAL_WIDTH,
                          initial_indent = tabstop1,
                          subsequent_indent = tabstop2)

    lines = '\n'.join(lines)
    print(lines)

select_from_combined()
