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
@dataclass(frozen=True)
class Action:
    action: ActionType
    index: int
    datatype: DataType

    @staticmethod
    def parse_input(input_val):
        pattern = r'^(?:([A-Za-z])?(\d)?(\d)([A-Za-z])|([A-Za-z]))$'

        if input_val == '':
            return None

        input_parsed = re.match(pattern, input_val, re.IGNORECASE)
        if input_parsed is None:
            raise ActionError(f'"{input_val}" is an invalid input.')

        action1, num1, num2, datatype, action2 = input_parsed.groups()
        if action2:
            match action2:
                case 'u' | 'U':
                    return Action(ActionType.UNDO, None, None)
                case 'n' | 'N':
                    return Action(ActionType.NEXT, None, None)
                case 'p' | 'P':
                    return Action(ActionType.PREVIOUS, None, None)
                case _:
                    raise ActionError(f'"{action2}" is an invalid action.')

        index = int((num1 or '') + num2)
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
            case _:
                raise ActionError(f'"{datatype}" is an invalid data type.')

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

# __next__ is always called before enter
# each enter must have a corresponding exit
class HeadingIterator:
    def __init__(self, data : dict, shuffle_start = False):
        self.printed_depth = 0
        self.path = [data]

        self.iterators = [0]
        self.lengths = [len(data)]
        if shuffle_start:
            self.vals = [random.sample(data.keys(), len(data))]
        else:
            self.vals = [list(data.keys())]

    def __iter__(self):
        return self

    def __next__(self):
        if self.iterators[-1] >= self.lengths[-1]:
            raise StopIteration
        
        self.iterators[-1] += 1
        print('in __next__', self.iterators)
        return self.vals[-1][self.iterators[-1] - 1]

    def previous(self):
        print(self.iterators, self.vals)
        self.iterators[-1] -= 1
        while self.iterators[-1] < 0:
            self.exit()
            self.iterators[-1] -= 1
            self.enter()
            self.iterators[-1] = self.lengths[-1] - 1
        print(self.iterators, self.vals)



    def enter(self, val = None):
        self.path.append(self.path[-1][self.vals[-1][self.iterators[-1] - 1]])
        self.iterators.append(0)

        if isinstance(self.path[-1], dict):
            self.vals.append(list(self.path[-1].keys()))
            self.lengths.append(len(self.vals[-1]))
        else:
            self.vals.append(None)
            self.lengths.append(0)

    def exit(self):
        self.path.pop()
        self.iterators.pop()
        self.lengths.pop()
        self.vals.pop()
        if self.printed_depth  >= len(self.path):
            self.printed_depth = len(self.path) - 1

    def print(self, skip_last_num = 0):
        for i in range(self.printed_depth, len(self.vals) - 1 - skip_last_num):
            print_wrapped(self.vals[i][self.iterators[i] - 1], i)
        self.printed_depth = len(self.vals) - 1

    def print_current(self):
        print_wrapped(self.vals[-2][self.iterators[-1] - 1], len(self.vals) - 2)

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

    heading = HeadingIterator(combined, False)
    for state in heading:
        logs['seen'][state] = logs['seen'].get(state, dict())
        if '.complete' in logs['seen'][state]:
            continue

        heading.enter(state)
        for category in heading:
            logs['seen'][state][category] = logs['seen'][state].get(category, [])

            heading.enter(category)

            if category == 'notes':
                if next(heading, None):
                    heading.enter(category)
                    heading.print(1)
                    print_wrapped(combined[state]['notes']['value'], 2)
                    heading.exit()
                heading.exit()
                continue

            for subcategory in heading:
                print(logs['seen'])
                if subcategory in logs['seen'][state][category]:
                    print('here')
                    continue

                print(state, category, subcategory)
                info = Info.flatten_info(combined[state][category][subcategory])
                if info is None:
                    continue

                heading.enter(subcategory)
                heading.print()
                info.print()
                action = perform_selection(info, selected, heading)
                logs['seen'][state][category].append(subcategory)
#                save_selection(selected, logs)
                heading.exit()

                if action == ActionType.PREVIOUS:
                    logs['seen'][state][category].pop()
                    print(logs['seen'])
                    heading.previous()
                    heading.previous()
                    heading.previous()
                    break;
            heading.exit()
        heading.exit()

def perform_selection(info, selected, heading):
    def reprint():
        heading.print_current()
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
                break
            case ActionType.PREVIOUS:
                return ActionType.PREVIOUS


def save_selection(selected, logs):
    with open(SELECTED, 'w') as file:
        json.dump(selected, indent=1)
    with open(COMBINE_LOGS, 'w') as file:
        json.dump(logs, indent=1)

select_from_combined()
