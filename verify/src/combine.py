#!/usr/bin/env python
import os, time
import json, csv
import re
from enum import Enum

from util import get_most_recent_rdirs
from constants import *
import test_suite

import pprint

# DUMPS
def dump_search_results():
    results = get_parsed(get_queries_from_search())
    with open(SEARCH_RESULTS_JSON, 'w') as file:
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
    with open(SEARCH_RESULTS_PARSED, 'r') as file:
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

# COMBINING
def map_to_questions():
    with open(AIRTABLE_TO_QUESTIONS, 'r') as file:
        airtable_map = json.load(file)
    with open(QUERIES_TO_QUESTIONS, 'r') as file:
        queries_map = json.load(file)
    with open(SEARCH_RESULTS_JSON, 'r') as file:
        search_results_json = json.load(file)
    with open(AIRTABLE_RESULTS_JSON, 'r') as file:
        airtable_results_json = json.load(file)

    states = dict()

    # accounts for missing states in either list & duplicates in Airtable
    states_list = sorted(list(search_results_json.keys() | airtable_results_json.keys()))

    for state in states_list:
        if state != 'Connecticut': continue
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

    pprint.pp(states, width=180)
#    test_suite.dump_and_diff('airtable_parse', states)

def add_subcategories(parse_method, state_dict_subcat, state_result_dict):
    if state_dict_subcat != '':
        if state_dict_subcat == 'checked':
            state_result_dict['value'] = True
        else:
            val = None
            match parse_method:
                case 'full':
                    val = parse_input(state_dict_subcat)
                    if len(val) == 1 and 'blank' in val:
                        val = val['blank']
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

# PARSING TEXT
URL_PATTERN = re.compile(
    r'https?://.*?(?=https?://|$|\s|[<>"\'])',
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
    blockList = []
    blockDict = dict()

    def __init__(self, block: str, setup = True):
        self.block = block
        self.source = self._extractSource() if setup else None
        
        self.id = None
        self.idType = None
        self.val = None

        self.title = None

        if setup:
            ExtractedBlock.blockList.append(self)

    def extract(self):
        if self._extractFromTitle():
            self._removeSourceFromVal()
            return True

        self.val = self.block

        if self.source:
            self._removeSourceFromVal()
            self._setMultipleSources()

            return True

        self.id = 'blank'
        self.idType = BlockIdType.BLANK
        return False

    @staticmethod
    def resetBlocks():
        ExtractedBlock.blockList = []
        ExtractedBlock.blockDict = dict()

    @staticmethod
    def mergeBlocks():
        blocks = ExtractedBlock.blockList
        merged_blocks = ExtractedBlock.blockDict

        merge_start = 0
        hit_link = None
        merged_blocks['blank'] = []

#        print([repr(block.val) for block in blocks])
        for i in range(len(blocks)):
            print(f'{i} - "{blocks[i].id}", "{repr(blocks[i].val)}", "{blocks[i].idType}"')
            match blocks[i].idType:
                case BlockIdType.TITLE:
                    if hit_link is not None:
                        ExtractedBlock._addMultiple(blocks[merge_start:hit_link+1])
                        hit_link = None
                    else:
                        merged_blocks['blank'] += [block.val for block in blocks[merge_start:i]]
                    blocks[i]._addToDict()
                    merge_start = i + 1
                case BlockIdType.SOURCE_ONLY | BlockIdType.MULTIPLE_SOURCES_ONLY:
                    hit_link = i
                case BlockIdType.SOURCE | BlockIdType.MULTIPLE_SOURCES:
                    if hit_link is not None:
                        ExtractedBlock._addMultiple(blocks[merge_start:hit_link+1])
                    hit_link = i
                    merge_start = i

                case BlockIdType.BLANK:
                    if hit_link is not None:
                        ExtractedBlock._addMultiple(blocks[merge_start:hit_link+1])
                        hit_link = None
                        merge_start = i

        if blocks[-1].idType == BlockIdType.BLANK:
            merged_blocks['blank'] += [block.val for block in blocks[merge_start:]]
        if hit_link is not None:
            ExtractedBlock._addMultiple(blocks[merge_start:hit_link+1])

        if merged_blocks['blank'] == []:
            merged_blocks.pop('blank')

    @staticmethod
    def getMerged():
        return ExtractedBlock.blockDict

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
        #         source = URL_PATTERN.search(self.block)
        source = URL_PATTERN.findall(self.block)
#        if source:
#            return source.group(0).strip().rstrip('",.)')
#        return None
        return source

    # @def Removes all sources stored in self.source from self.val 
    def _removeSourceFromVal(self):
        if self.source is None: return

        if len(self.source) == 1:
            self.val = self._cleanAnalysis(self.val.replace(self.source[0], ''))
        else:
            self.val = self.block
            for source in self.source:
                self.val = self.val.replace(source, '')
            self.val = self._cleanAnalysis(self.val)

    def _resolveIDConflicts(self):
        i = 1
        candidate = self.id
        while candidate in ExtractedBlock.blockDict:
            candidate = f'{self.id}_{i}'
            i += 1
        self.id = candidate

    def _setMultipleSources(self):
        if len(self.source) == 1:
            self.id = self.source[0]
            self.idType = BlockIdType.SOURCE if self.val else BlockIdType.SOURCE_ONLY
        else:
            self.id = 'multiple_sources'
            self.idType = BlockIdType.MULTIPLE_SOURCES if self.val else BlockIdType.MULTIPLE_SOURCES_ONLY

    @staticmethod
    def _cleanAnalysis(text: str) -> str:
        return text.strip()

    def _addToDict(self):
        self._resolveIDConflicts()
        ExtractedBlock.blockDict[self.id] = {'value' : self.val, 'source' : self.source}

    @staticmethod
    def _addMultiple(blocks):
        block = ExtractedBlock('', setup = False)
        block.source = []
        block.val = ''
#        block = blocks[0]
        for next_block in blocks:
            block.block += next_block.block
            block.val += next_block.val
            block.source += next_block.source
            block.id = next_block.id

        block._setMultipleSources()
        block._addToDict()

def clean_analysis(block: str) -> str:
#    text = URL_PATTERN.sub("", text)
    return text.strip()


def parse_input(text: str) -> dict:
    result = {}
    result_list = []
    blank = []

#    blocks = re.split(r"\n\s*\n+", text)
    blocks = re.split(r"\n\s*\n+|(?<=\S)(?=https?://)", text)
    sections = re.split(r"(?:\r?\n\s*){2,}", text.strip())
    print('\t\t', blocks)
    ExtractedBlock.resetBlocks()

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        extracted_block = ExtractedBlock(block)
        extracted_block.extract()

    ExtractedBlock.mergeBlocks()

    return ExtractedBlock.getMerged()

map_to_questions()
