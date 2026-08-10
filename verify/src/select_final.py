#!/usr/bin/env python
import os
import json
import re
import random
from enum import Enum, StrEnum
from dataclasses import dataclass
from urllib.parse import urlparse

from prompt_toolkit import prompt

from util import print_wrapped, TABSIZE
from constants import *
import test_suite

random.seed(RANDOM_SEED)

@dataclass
class Info:
    airtable: list
    google: list
    notes: str

    airtable_refs: list

    airtable_merged: list
    google_merged: list
    airtable_edited: list
    history: list

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

        if not airtable_flattened and not airtable_refs and not google_sources:
            return None

        return Info(airtable_flattened, 
                    google_sources, 
                    '; '.join(google_notes),
                    airtable_refs, 
                    [ False for val in airtable_flattened ],
                    [ False for val in google_sources ],
                    [ None for val in airtable_flattened ],
                    [])

    def undo(self, selection):
        last_action = self.history[-1]

    def merge(self, action):
        mergedlist = f'{action.datatype}_merged'
        getattr(self, mergedlist)[action.index] = not getattr(self, mergedlist)[action.index]

    def edit(self, action, replacement):
        editlist = f'{action.datatype}_edited'
        getattr(self, editlist)[action.index] = replacement

    def print(self):
        for i in range(len(self.airtable)):
            merged = '*' if self.airtable_merged[i] else ''
            edited = '~' if self.airtable_edited[i] else ''
            val = f'{edited}{merged}{str(i)}a - {self.airtable_edited[i] or self.airtable[i]}'
            
            dedent = (1 if merged else 0) + (1 if edited else 0) - (1 if i < 10 else 0)
            print_wrapped(val, 3, 0, -dedent, 6 + dedent)
        if self.airtable:
            print()

        for i in range(len(self.google)):
            merged = '*' if self.google_merged[i] else ''
            dedent = (1 if merged else 0) - (1 if i < 10 else 0)
            print_wrapped(f'{merged}{str(i)}g - {self.google[i]}', 3, 0, -dedent, 6)

        if self.notes:
            print()
            print_wrapped(self.notes, 3)

# --------------------------------- CLI -------------------------------- #
@dataclass
class Action:
    action: ActionType
    index: int
    datatype: DataType

    # allow 3 types of inputs:
    #   [action]#<a/g>      action is performed on Airtable/Google #; merge assumed
    #   #<a/g><n/p/u>       merge is performed on Airtable/Google #; then next/previous/undo
    #   n/p/u               next/previous/undo
    @staticmethod
    def parse_input(input_val):
        pattern = r'^(?:([A-Za-z])?(\d)?(\d)([A-Za-z])([A-Za-z])?|([A-Za-z]))$'

        if input_val == '':
            return None

        input_parsed = re.match(pattern, input_val, re.IGNORECASE)
        if input_parsed is None:
            raise ActionError(f'"{input_val}" is an invalid input.')

        action1, num1, num2, datatype, action2, action3 = input_parsed.groups()

        index = int((num1 or '') + num2) if num2 else None
        match action1:
            case None | 'm' | 'M':
                action1 = ActionType.MERGE
                action1 = ActionType.MERGE
            case 'e' | 'E':
                action1 = ActionType.EDIT
            case 'u' | 'U':
                action1 = ActionType.UNDO
            case _:
                raise ActionError(f'"{action1}" is an invalid action.')
        
        match datatype:
            case 'a' | 'A':
                datatype = DataType.AIRTABLE
            case 'g' | 'G':
                datatype = DataType.GOOGLE
            case None:
                pass
            case _:
                raise ActionError(f'"{datatype}" is an invalid data type.')

        if action2 or action3:
            match action2 or action3:
                case 'u' | 'U':
                    return Action(ActionType.UNDO, index, datatype)
                case 'n' | 'N':
                    return Action(ActionType.NEXT, index, datatype)
                case 'p' | 'P':
                    return Action(ActionType.PREVIOUS, index, datatype)
                case _:
                    raise ActionError(f'"{action2}" is an invalid action.')

        return Action(action1, index, datatype)

class ActionError(Exception):
    pass

class ActionType(Enum):
    MERGE = 0
    EDIT = 1
    UNDO = 2
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

        self.reverse = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.reverse:
            self.previous()
        else:
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
        with open(SELECTED, 'r') as file:
            selected = json.load(file)
    except FileNotFoundError:
        selected = dict()

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

#        print(state, category, subcategory, heading_type, heading)

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
                    continue

                headings.enter() # enter the subcategory scope

                if len(info_list) > info_index:
                    info = info_list[info_index] # use cached
                else:
                    info = Info.flatten_info(headings.get_val())
                    info_list.insert(info_index, info)
                info_index += 1
                if info is None:
                    continue

                headings.print()
                info.print()
                action = perform_selection(info, selected, headings)
                logs['seen'][state][category].append(subcategory)
#                save_selection(selected, logs)
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
                        pass

def perform_selection(info, selected, heading):
    def reprint():
        print_wrapped(heading.get_heading(2), 2)
        info.print()

    while True:
        try:
            action = Action.parse_input(input('> '))
        except ActionError as e:
            print(e)
            continue
        if action is None:
            continue

        match action.action:
            case ActionType.MERGE:
                try:
                    info.merge(action)
                    reprint()
                except IndexError:
                    print("Out of bounds index selected.")
            case ActionType.EDIT:
                if action.datatype != DataType.AIRTABLE:
                    print("Only Airtable can be edited.")
                    continue
                new_text = prompt("> ", default=info.airtable[action.index])
                info.edit(action, new_text)
                reprint()
            case ActionType.UNDO:
                pass
            case ActionType.NEXT:
                if action.datatype is not None: # merge and then next
                    action.action = ActionType.MERGE
                    info.merge(action)
                break
            case ActionType.PREVIOUS:
                if action.datatype is not None: # merge and then previous
                    action.action = ActionType.MERGE
                    info.merge(action)
                return ActionType.PREVIOUS


def save_selection(selected, logs):
    with open(SELECTED, 'w') as file:
        json.dump(selected, indent=1)
    with open(COMBINE_LOGS, 'w') as file:
        json.dump(logs, indent=1)

select_from_combined()
