#!/usr/bin/env python
import os
import json
import re
import random
from enum import Enum, StrEnum, IntEnum
from dataclasses import dataclass
from urllib.parse import urlparse

from prompt_toolkit import prompt

from util import print_wrapped, TABSIZE
from constants import *
import test_suite

import pprint

random.seed(RANDOM_SEED)

@dataclass
class Info:
    airtable: list
    google: list
    notes: str

    airtable_refs: list
    airtable_keys: list

    airtable_merged: list
    google_merged: list
    airtable_edited: list

    @staticmethod
    def flatten_info(info) -> Info:
        value = info.get('value')
        airtable_sources = info.get('AirtableSource')
        google_sources = info.get('GoogleSource', [])
        google_notes = info.get('GoogleNotes', [])

        airtable_flattened = []
        airtable_refs = []
        airtable_keys = []

        def add_blocks(blocks, key_prefix):
            for i in range(len(blocks)):
                block = blocks[i]
                if 'title' in block:
                    airtable_flattened.append(block['title'])
                    airtable_refs.append(i)
                    airtable_keys.append((key_prefix, 'title'))
                if 'value' in block:
                    airtable_flattened.append(block['value'])
                    airtable_refs.append(i)
                    airtable_keys.append((key_prefix, 'value'))
                for source in block.get('source', []):
                    airtable_flattened.append(source)
                    airtable_refs.append(i)
                    airtable_keys.append((key_prefix, 'source'))

        if isinstance(value, list):
            if isinstance(value[0], dict):
                add_blocks(value, 'value')
            else:
                airtable_flattened.append(', '.join(value))
                airtable_refs.append(None)
                airtable_keys.append(('value', value))
        elif isinstance(value, str):
            airtable_flattened.append(value)
            airtable_refs.append(None)
            airtable_keys.append(('value', None))

        if airtable_sources is not None:
            add_blocks(airtable_sources, 'AirtableSource')
            # reconstructed as ['AirtableSource'][list_index]['title'/'value'/'source']

        if not airtable_flattened and not airtable_refs and not google_sources:
            return None

        return Info(airtable_flattened, 
                    google_sources, 
                    '; '.join(google_notes),
                    airtable_refs, 
                    airtable_keys,
                    [ MergeStatus.UNMERGED for val in airtable_flattened ],
                    [ MergeStatus.UNMERGED for val in google_sources ],
                    [ None for val in airtable_flattened ])

    def flag(self, action):
        mergedlist = f'{action.datatype}_merged'
        if getattr(self, mergedlist)[action.index] == MergeStatus.FLAGGED:
            getattr(self, mergedlist)[action.index] = MergeStatus.UNMERGED
        else:
            getattr(self, mergedlist)[action.index] = MergeStatus.FLAGGED

    def merge(self, action):
        mergedlist = f'{action.datatype}_merged'
        if getattr(self, mergedlist)[action.index] == MergeStatus.MERGED:
            getattr(self, mergedlist)[action.index] = MergeStatus.UNMERGED
        else:
            getattr(self, mergedlist)[action.index] = MergeStatus.MERGED

    def edit(self, action, replacement):
        editlist = f'{action.datatype}_edited'
        getattr(self, editlist)[action.index] = replacement

    def print(self):
        for i in range(len(self.airtable)):
            merged = '*' if self.airtable_merged[i] == MergeStatus.MERGED else ''
            flagged = '+' if self.airtable_merged[i] == MergeStatus.FLAGGED else ''
            edited = '~' if self.airtable_edited[i] else ''
            val = f'{edited}{merged}{flagged}{str(i)}a - {self.airtable_edited[i] or self.airtable[i]}'
            
            dedent = (1 if merged else 0) + (1 if flagged else 0) + (1 if edited else 0) - (1 if i < 10 else 0)
            print_wrapped(val, 3, 0, -dedent, 6 + dedent)
        if self.airtable:
            print()

        for i in range(len(self.google)):
            merged = '*' if self.google_merged[i] == MergeStatus.MERGED else ''
            flagged = '+' if self.google_merged[i] == MergeStatus.FLAGGED else ''

            dedent = (1 if merged else 0) + (1 if flagged else 0) - (1 if i < 10 else 0)
            print_wrapped(f'{merged}{flagged}{str(i)}g - {self.google[i]}', 3, 0, -dedent, 6)

        if self.notes:
            print()
            print_wrapped(self.notes, 3)

    # reconstructed as ['AirtableSource'][list_index]['title'/'value'/'source']
    def export(self):
        export_dict = {'value' : 
                            { MergeStatus.MERGED : [], MergeStatus.FLAGGED : []}, 
                       'AirtableSource' : 
                            { MergeStatus.MERGED : [], MergeStatus.FLAGGED : []}
                      }

        for i in range(len(self.airtable_merged)):
            merge_status = self.airtable_merged[i]
            if merge_status == MergeStatus.UNMERGED:
                continue

            pprint.pprint(self.airtable_keys)
            L = export_dict[self.airtable_keys[i][0]][merge_status]
            L.append({'val' : self.airtable_edited[i] or self.airtable[i],
                      'ref' : self.airtable_refs[i],
                      'key' : self.airtable_keys[i][1:]})

        def normalize(L):
            rank = -1
            previous = None

            for i, value in enumerate(L):
                print(value)
                if value['ref'] != previous:
                    rank += 1
                    previous = value['ref']
                L[i] = {'val' : value['val'],
                        'ref' : rank,
                        'key' : value['key']}
            return L

        def structure(L):
            M = []
            for item in L:
                val = item['val']
                print('val', val)
                index = item['ref']
                key = item['key'][0]
                if index < len(M):
                    if isinstance(M[index].get(key), str):
                        M[index][key] = [M[index][key]]
                        M[index][key].append(val)
                    else:
                        M[index][key] = val
                else:
                    M.append(dict())
                    M[index][key] = val
            L[:] = M

        for mergetype in (MergeStatus.MERGED, MergeStatus.FLAGGED):
            value_list = export_dict['value'][mergetype]
            if len(value_list) == 1 and value_list[0]['ref'] is None:
                if value_list[0]['key'][0]: # use the stored list
                    export_dict['value'][mergetype] = value_list[0]['key'][0]   
                else:                       # use the str
                    export_dict['value'][mergetype] = value_list[0]['val']
            else:
                normalize(value_list)
                structure(value_list)

            airtable_list = export_dict['AirtableSource'][mergetype]
            normalize(airtable_list)
            structure(airtable_list)


        google_merged = [self.google[i] for i in range(len(self.google)) 
                         if self.google_merged[i] == MergeStatus.MERGED]
        google_flagged = [self.google[i] for i in range(len(self.google)) 
                          if self.google_merged[i] == MergeStatus.FLAGGED]

        merge_dict = dict()
        if export_dict['value'][MergeStatus.MERGED]: 
            merge_dict['value'] = export_dict['value'][MergeStatus.MERGED]
        if export_dict['AirtableSource'][MergeStatus.MERGED]: 
            merge_dict['AirtableSource'] = export_dict['AirtableSource'][MergeStatus.MERGED]
        if google_merged: 
            merge_dict['GoogleSource'] = google_merged

        flagged_dict = dict()
        if export_dict['value'][MergeStatus.FLAGGED]: 
            flagged_dict['value'] = export_dict['value'][MergeStatus.FLAGGED]
        if export_dict['AirtableSource'][MergeStatus.FLAGGED]: 
            flagged_dict['AirtableSource'] = export_dict['AirtableSource'][MergeStatus.FLAGGED]
        if google_flagged: 
            flagged_dict['GoogleSource'] = google_flagged

        return (merge_dict, flagged_dict)

class MergeStatus(IntEnum):
    UNMERGED = 0
    MERGED = 1
    FLAGGED = 2

# --------------------------------- CLI -------------------------------- #
@dataclass
class Action:
    edit_action: ActionType
    move_action: ActionType
    save: bool
    index: int
    datatype: DataType

    # allow 3 types of inputs:
    #   [action]#<a/g>      action is performed on Airtable/Google #; merge assumed
    #   #<a/g><n/p/u>       merge is performed on Airtable/Google #; then next/previous
    #   n/p/u               next/previous
    @staticmethod
    def parse_input(input_val):
        pattern = r'^(?:([mMeEfF])?(\d)?(\d)([gGaA])([nNpP])?|([nNpP])?)([sS])?$'

        if input_val == '':
            return None

        input_parsed = re.match(pattern, input_val, re.IGNORECASE)
        if input_parsed is None:
            raise ActionError(f'"{input_val}" is an invalid input.')

        e_action, num1, num2, datatype, m_action1, m_action2, save = input_parsed.groups()
        save = save or False

        index = int((num1 or '') + num2) if num2 else None
        match e_action:
            case None if index is not None:
                e_action = ActionType.MERGE
            case None:
                e_action = None
            case 'm' | 'M':
                e_action = ActionType.MERGE
            case 'e' | 'E':
                e_action = ActionType.EDIT
            case 'f' | 'F':
                e_action = ActionType.FLAG
            case _:
                raise ActionError(f'"{e_action}" is an invalid action.')
        
        match datatype:
            case 'a' | 'A':
                datatype = DataType.AIRTABLE
            case 'g' | 'G':
                datatype = DataType.GOOGLE
            case None:
                pass
            case _:
                raise ActionError(f'"{datatype}" is an invalid data type.')

        if m_action1 or m_action2:
            match m_action1 or m_action2:
                case 'n' | 'N':
                    return Action(e_action, ActionType.NEXT, save, index, datatype)
                case 'p' | 'P':
                    return Action(e_action, ActionType.PREVIOUS, save, index, datatype)
                case _:
                    raise ActionError(f'"{m_action1 or m_action2}" is an invalid action.')

        return Action(e_action, None, save, index, datatype)

class ActionError(Exception):
    pass

class ActionType(Enum):
    MERGE = 0
    EDIT = 1
    FLAG = 2
    NEXT = 3
    PREVIOUS = 4
   

class DataType(StrEnum):
    AIRTABLE = 'airtable'
    GOOGLE = 'google'
# ---------------------------------------------------------------------- #

class HeadingIterator:
    def __init__(self, data : dict, shuffle_start = False):
        self.depth = 1              #assert self.depth == len(self.path) == ...
        self.printed_depth = 0
        self.path = [data]

        self.iterators = [-1]
        self.lengths = [len(data)]
        if shuffle_start:
            self.vals = [random.sample(data.keys(), len(data))]
        else:
            self.vals = [list(data.keys())]

    def __iter__(self):
        return self

    def __next__(self):
        self.iterators[-1] += 1
        while self.iterators[-1] >= self.lengths[-1]:
            self.exit()
            if self.depth == 0:
                raise StopIteration
            self.iterators[-1] += 1
        
        return self.vals[-1][self.iterators[-1]]

    def previous(self, _is_recursive_call = False):
        self.iterators[-1] -= 1
        if self.depth == 1:
            raise StopIteration

        if self.iterators[-1] < 0:
            self.exit()
            self.previous(True)

        if _is_recursive_call:
            self.enter()
            self.iterators[-1] = self.lengths[-1] - 1
            if self.iterators[-1] < 0:
                self.exit()
                self.previous(True)

    def enter(self, val = None):
        self.path.append(self.path[-1][self.vals[-1][self.iterators[-1]]])
        self.iterators.append(-1)

        if isinstance(self.path[-1], dict):
            self.vals.append(list(self.path[-1].keys()))
            self.lengths.append(len(self.vals[-1]))
        else:
            self.vals.append(None)
            self.lengths.append(0)

        self.depth += 1

    def exit(self):
        self.path.pop()
        self.iterators.pop()
        self.lengths.pop()
        self.vals.pop()
        self.depth -= 1
        if self.printed_depth  >= self.depth:
            self.printed_depth = self.depth - 1

    def print(self, skip_last_num = 0):
        for i in range(self.printed_depth, self.depth - 1 - skip_last_num):
            print_wrapped(self.vals[i][self.iterators[i]], i)
        self.printed_depth = self.depth - 1

    def get_heading(self, layer = -1):
        if layer >= self.depth:
            return None
        return self.vals[layer][self.iterators[layer]]

    def get_val(self):
        return self.path[-1]

    def get_depth(self):
        return self.depth

class HeadingType(Enum):
    STATE = 1
    CATEGORY = 2
    SUBCATEGORY = 3
    VALUE = 4

def select_from_combined():
    with open(COMBINED_RESULTS, 'r') as file:
        combined = json.load(file)

    try:
        with open(COMBINE_LOGS, 'r') as file:
            logs = json.load(file)
    except FileNotFoundError:
        logs = dict()
    logs['seen'] = logs.get('seen', dict())

    try:
        with open(MERGED, 'r') as file:
            merged = json.load(file)
    except FileNotFoundError:
        merged = dict()
    try:
        with open(FLAGGED, 'r') as file:
            flagged = json.load(file)
    except FileNotFoundError:
        flagged = dict()

    for state in merged:
        for category in merged[state]:
            for subcategory in merged[state][category]:
                combined[state][category][subcategory] |= merged[state][category][subcategory]

    state, category, subcategory = None, None, None
    headings = HeadingIterator(combined, False)
    heading_type = None

    info_list = []
    info_index = 0

    def get_headings():
        return (headings.get_heading(0), 
                headings.get_heading(1),
                headings.get_heading(2))

    for heading in headings:
        heading_type = HeadingType(headings.get_depth())
        state, category, subcategory = get_headings()

        match heading_type:
            case HeadingType.STATE:
                logs['seen'][state] = logs['seen'].get(state, dict())
                if '.complete' in logs['seen'][state]:
                    continue
                headings.enter() # next iteration is in category

            case HeadingType.CATEGORY:
                logs['seen'][state][category] = logs['seen'][state].get(category, [])
                
                headings.enter() # next iteration is in subcategory

            case HeadingType.SUBCATEGORY:
                if category == 'notes':
                    headings.enter(category)
                    headings.print(1)
                    print_wrapped(headings.get_val(), 2)
                    continue

                if subcategory in logs['seen'][state][category]:
                    info_list.insert(info_index, False) # placeholder
                    info_index += 1
                    continue

                headings.enter() # enter the subcategory scope

                if info_index < len(info_list):
                    if info_list[info_index] is False:
                        info_list[info_index] = Info.flatten_info(headings.get_val())
                    info = info_list[info_index] # use cached
                else:
                    info = Info.flatten_info(headings.get_val())
                    info_list.insert(info_index, info)
                info_index += 1
                if info is None:
                    continue

                headings.print()
                info.print()
                action = None
                while action is None:
                    action, save = perform_selection(info, headings)
                    if save:
                        save_selection(merged,
                                       flagged,
                                       info_list[info_index - 1], 
                                       (state, category, subcategory),
                                       logs)

                logs['seen'][state][category].append(subcategory)
                headings.exit() # exit to a category's scope

                if action == ActionType.PREVIOUS:
                    logs['seen'][state][category].pop()

                    try:
                        headings.previous()
                        state, category, subcategory = get_headings()
                        if subcategory in logs['seen'][state][category]:
                            logs['seen'][state][category].remove(subcategory)
                        if category == 'notes':
                            headings.previous()
                        while (Info.flatten_info(combined[state][category][subcategory])) is None:
                            headings.previous()
                            state, category, subcategory = get_headings()
                            if subcategory in logs['seen'][state][category]:
                                logs['seen'][state][category].remove(subcategory)
                            info_index -= 1
                        headings.previous()
                        info_index -= 2
                    except StopIteration:
                        info_index -= 1

def perform_selection(info, heading):
    def reprint():
        print_wrapped(heading.get_heading(2), 2)
        info.print()

    try:
        action = Action.parse_input(input('> '))
    except ActionError as e:
        print(e)
        return None, False
    if action is None:
        return None, False

    match action.edit_action:
        case ActionType.MERGE:
            try:
                info.merge(action)
                if action.move_action is None:
                    reprint()
            except IndexError:
                print("Out of bounds index selected.")
        case ActionType.FLAG:
            try:
                info.flag(action)
                if action.move_action is None:
                    reprint()
            except IndexError:
                print("Out of bounds index selected.")
        case ActionType.EDIT:
            if action.datatype != DataType.AIRTABLE:
                print("Only Airtable can be edited.")
                return None, False
            new_text = prompt("> ", default=info.airtable[action.index])
            info.edit(action, new_text)
            if action.move_action is None:
                reprint()

    return action.move_action, action.save

def save_selection(merged, flagged, info, headings, logs):
    merged_info, flagged_info = info.export()
    print()
    print(f'{merged_info=}')
    print(f'{flagged_info=}')

    state, category, subcategory = headings
    if merged_info:
        merged[state] = merged.get(state, dict())
        merged[state][category] = merged.get(category, dict())
        merged[state][category][subcategory] = merged_info
        with open(MERGED, 'w') as file:
            json.dump(merged, file, indent=1)
    if flagged_info:
        flagged[state] = flagged.get(state, dict())
        flagged[state][category] = flagged.get(category, dict())
        flagged[state][category][subcategory] = flagged_info
        print(flagged[state][category])
        with open(FLAGGED, 'w') as file:
            json.dump(flagged, file, indent=1)

    with open(COMBINE_LOGS, 'w') as file:
        json.dump(logs, file, indent=1)

select_from_combined()
