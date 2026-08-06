#!/usr/bin/env python
import os, time, shutil
import json, csv
import re
from enum import Enum
from urllib.parse import urlparse

from util import get_most_recent_rdirs
from constants import *
import test_suite

import pprint

# DUMPS
def dump_search_results():
    results = get_parsed(get_queries_from_search())
    with open(SEARCH_RESULTS_PARSED, 'w') as file:
        json.dump(results, file, indent=1)

def dump_airtable_results():
    results = get_airtable()
    with open(AIRTABLE_RESULTS_JSON, 'w') as file:
        json.dump(results, file, indent=1)

# STRUCTURING DATA
def get_queries_from_search() -> dict():
    states = dict()
    rdirs = get_most_recent_rdirs(SEARCH_RESULTS_PATH)
    for rdir in rdirs:
        state = rdir[:rdir.find('_')]
        rdir = os.path.join(SEARCH_RESULTS_PATH, rdir)

        queries = dict()
        for query_dir in os.listdir(rdir):
            query_json = os.path.join(rdir, query_dir, f'{query_dir}.json')
            if not os.path.exists(query_json): continue

            with open(query_json, 'r') as file:
                query_results = json.load(file)
            if 'items' not in query_results: continue

            links = []
            for website in query_results['items']:
                links.append(website['link'])
                
            queries[int(query_dir)] = links
        states[state] = queries
    return states

def get_parsed(queries) -> dict():
    with open(SEARCH_RESULTS_HUMAN_PARSED, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        header = list(set(header[2:]))
        header.remove('TRUE')
        header.sort()

        states = { state : 
                  { i : {'links' : [], 'notes' : None } for i in range(16) }
                  for state in header }
        states_index_map = { header.index(s) : s for s in header }

        for question in range(16):
            for link in range(11):
                link_row = next(reader)[2:]
                for i in range(0, len(link_row), 2):
                    if link_row[i+1] == 'TRUE':
                        state = states_index_map[i//2]
                        if link != 10:
                            states[state][question]['links'].append(queries[state][question][link])
                        else:
                            states[state][question]['links'].append(link_row[i])

            notes = next(reader)[2:]
            for i in range(0, len(notes), 2):
                if notes[i] != '':
                    states[states_index_map[i//2]][question]['notes'] = notes[i]

            if question != 15: next(reader)

    return states

def get_airtable() -> dict():
    with open(AIRTABLE_TO_JSON, 'r') as file:
        airtable_map = json.load(file)

    states = {}
    with open(AIRTABLE_RESULTS, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)

        for row in reader:
            state = row[0].strip()
            if state == 'DC': state = "District of Columbia"
            if state in states:
                state = state + "_1"
            states[state] = {}
            for i in range(len(row)):
                states[state][airtable_map[str(i)]] = row[i].strip()

    return states

# PARSING AIRTABLE
def parse_airtable():
    with open(AIRTABLE_TO_QUESTIONS, 'r') as file:
        airtable_map = json.load(file)
    with open(SEARCH_RESULTS_PARSED, 'r') as file:
        search_results_parsed = json.load(file)
    with open(AIRTABLE_RESULTS_JSON, 'r') as file:
        airtable_results_json = json.load(file)

    states = dict()

    # accounts for missing states in either list & duplicates in Airtable
    states_list = sorted(list(search_results_parsed.keys() | airtable_results_json.keys()))

    for state in states_list:
        states[state] = dict()
        state_dict = airtable_results_json.get(state)
        if state_dict is None: continue
        for category in airtable_map:
            states[state][category] = dict()
            for subcategory in airtable_map[category]:
                states[state][category][subcategory] = dict()
                state_result_dict = states[state][category][subcategory] 
                
                add_subcategories(airtable_map[category][subcategory]['parse_method'],
                                  state_dict[subcategory],
                                  state_result_dict)
                add_subsubcategories(airtable_map[category][subcategory], 
                                     state_dict,
                                     state_result_dict)

    test_suite.dump_and_diff('airtable_parse', states)

def parse_input(text: str) -> dict:
    blocks = split_text(text)
    ExtractedBlock.resetBlocks()

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        extracted_block = ExtractedBlock(block)
        extracted_block.extract()

    ExtractedBlock.mergeBlocks()
    return ExtractedBlock.getMerged()

def add_subcategories(parse_method, state_dict_subcat, state_result_dict):
    if state_dict_subcat != '':
        if state_dict_subcat == 'checked':
            state_result_dict['value'] = True
        else:
            val = None
            match parse_method:
                case 'full':
                    val = parse_input(state_dict_subcat)
                case 'split_comma':
                    val = [ x for x in next(csv.reader([state_dict_subcat], delimiter=',', quotechar='"')) ]

                case _:
                    val = state_dict_subcat
            state_result_dict['value'] = val

def add_subsubcategories(subcategory_map, state_dict, state_result_dict):
    if 'subsubcategories' not in subcategory_map: return
    subsubcat_map = subcategory_map['subsubcategories']

    if "Source" in subsubcat_map and state_dict[subsubcat_map["Source"]]:
        state_result_dict["AirtableSource"] = parse_input(state_dict[subsubcat_map["Source"]])

    if "Other" in subsubcat_map and state_dict[subsubcat_map["Other"]]:
        state_result_dict["AirtableOther"] = parse_input(state_dict[subsubcat_map["Other"]])

URL_PATTERN = re.compile(
    r'https?://(?:(?!https?://)[^\s<>"{}|\\^`\[\]])+',
    re.IGNORECASE,
)

class BlockIdType(Enum):
    TITLE = 0
    SOURCE = 1
    MULTIPLE_SOURCES = 2
    SOURCE_ONLY = 3
    MULTIPLE_SOURCES_ONLY = 4
    BLANK = 5

class ExtractedBlock:
    unmergedList = []
    blockList = []

    def __init__(self, block: str, setup = True):
        self.block = block
        self.source = self._extractSource() if setup else []
        
        self.id = None
        self.idType = None
        self.val = None

        self.title = None

        if setup:
            ExtractedBlock.unmergedList.append(self)

    def extract(self):
        if self._extractFromTitle():
            self._removeSourceFromVal()
            return True

        self.val = self.block

        if self.source:
            self._removeSourceFromVal()
            self._resolveMultipleSources()

            return True

        self.id = 'blank'
        self.idType = BlockIdType.BLANK
        return False

    @staticmethod
    def resetBlocks():
        ExtractedBlock.unmergedList = []
        ExtractedBlock.blockList = []

    @staticmethod
    def mergeBlocks():
        blocks = ExtractedBlock.unmergedList

        merge_start = 0
        merge_end = None

        for i in range(len(blocks)):
            match blocks[i].idType:
                case BlockIdType.TITLE:
                    if merge_end is None:
                        ExtractedBlock._addAsBlank(blocks[merge_start:i])
                    else:
                        ExtractedBlock._combineAndAddMultiple(blocks[merge_start:merge_end+1])
                    merge_start = i
                    merge_end = i
                case BlockIdType.SOURCE_ONLY | BlockIdType.MULTIPLE_SOURCES_ONLY:
                    merge_end = i
                case BlockIdType.SOURCE | BlockIdType.MULTIPLE_SOURCES:
                    if merge_end is None:
                        ExtractedBlock._addAsBlank(blocks[merge_start:i])
                    else:
                        ExtractedBlock._combineAndAddMultiple(blocks[merge_start:merge_end+1])
                    merge_start = i
                    merge_end = i

                case BlockIdType.BLANK:
                    if merge_end is not None:
                        ExtractedBlock._combineAndAddMultiple(blocks[merge_start:merge_end+1])
                        merge_start = i
                        merge_end = None

        if blocks[-1].idType == BlockIdType.BLANK:
            ExtractedBlock._addAsBlank(blocks[merge_start:])
        if merge_end is not None:
            ExtractedBlock._combineAndAddMultiple(blocks[merge_start:merge_end+1])

    @staticmethod
    def getMerged():
        return ExtractedBlock.blockList

    def _extractFromTitle(self):
        lines = [line.strip() for line in self.block.splitlines() if line.strip()]

        if not lines: return None

        first = lines[0]
        if first.endswith(":"):
            self.id = self.title = first[:-1].strip()
            self.val = self._cleanAnalysis(self.block.replace(first, ''))
            self.idType = BlockIdType.TITLE
            return True
        return False

    def _extractSource(self):
        source = URL_PATTERN.findall(self.block)
        return source

    # @def Removes all sources stored in self.source from self.val 
    def _removeSourceFromVal(self):
        if self.source == []: return

        if len(self.source) == 1:
            self.val = self._cleanAnalysis(self.val.replace(self.source[0], ''))
        else:
            self.val = self.block
            for source in self.source:
                self.val = self.val.replace(source, '')
            self.val = self._cleanAnalysis(self.val)

    def _resolveMultipleSources(self):
        if self.idType is BlockIdType.TITLE: return
        if len(self.source) == 1:
            self.id = self.source[0]
            self.idType = BlockIdType.SOURCE if self.val else BlockIdType.SOURCE_ONLY
        else:
            self.id = 'multiple_sources'
            self.idType = BlockIdType.MULTIPLE_SOURCES if self.val else BlockIdType.MULTIPLE_SOURCES_ONLY

    @staticmethod
    def _cleanAnalysis(text: str) -> str:
        return text.strip()

    def _addToList(self):
        if self.idType is BlockIdType.TITLE:
            block = { 'title' : self.id }
            if self.val:
                block['value'] = self.val
            if self.source:
                block['source'] = self.source
            ExtractedBlock.blockList.append(block)
        else:
            block = dict()
            if self.val:
                block['value'] = self.val
            block['source'] = self.source
            ExtractedBlock.blockList.append(block)

    @staticmethod
    def _addAsBlank(blocks):
        val = [block.val for block in blocks]
        if val == []: return
        ExtractedBlock.blockList.append({'value' : val})

    @staticmethod
    def _combineAndAddMultiple(blocks):
        block = ExtractedBlock('', setup = False)
        block.val = ''
        for next_block in blocks:
            block.block += next_block.block
            block.val += next_block.val
            block.source += next_block.source
            if block.idType is None:
                block.id = next_block.id
                block.idType = next_block.idType

        block._resolveMultipleSources()
        block._addToList()

def split_text(text: str) -> list[str]:
    url = r"https?://[^\s]+"

    # split on blank lines & after URLs
    parts = re.split(
        rf"\n\s*\n|({url})(?=\s|$)",
        text
    )

    # Remove empty entries and preserve all matched content
    result = [part for part in parts if part]

    # Split malformed glued URLs:
    # "texthttps://example.com" -> "text", "https://example.com"
    final = []
    for part in result:
        final.extend(re.split(r"(?<=\S)(?=https?://)", part))

    return [x for x in final if x]

# COMBINING
TERMINAL_WIDTH = shutil.get_terminal_size().columns

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
                if notes:
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
        logs['seen'][state] = logs['seen'].get(state, dict())
        for category in combined[state]:
            logs['seen'][state][category] = logs['seen'][state].get(category, [])
            for subcategory in combined[state][category]:
                if subcategory in logs['seen'][state][category]:
                    continue

def print_info(info, selected: list, modified: list):
    value = info.get('value')
    airtable_sources = info.get('AirtableSources')
    google_sources = info.get('GoogleSources')
    google_notes = info.get('GoogleNotes')

combine_airtable_and_search()
        
# select_from_combined()
