#!/usr/bin/env python
import os, time
import json, csv
import re

from util import get_most_recent_rdirs
from constants import *

import pprint

def split_string(response) -> list():
    split = response.splitlines()
    parsed = {}
    link_re = re.compile(r".*(http.*)")

    link = None
    val = ''
    for i in range(len(split)):
        match = link_re.match(split[i])
        if match:
            if link:
                parsed[link] = val if val != '' else None
                val = ''
            link = match[1]
        else:
            val = "\n".join(filter(None, [val, split[i]]))
    if val:
        parsed[link] = val if val != '' else None

    print(parsed)

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

#            print(states[state])

    return states

def dump_search_results():
    results = get_parsed(get_queries_from_search())
    with open(SEARCH_RESULTS_JSON, 'w') as file:
        json.dump(results, file, indent=1)

def dump_airtable_results():
    results = get_airtable()
    with open(AIRTABLE_RESULTS_JSON, 'w') as file:
        json.dump(results, file, indent=1)

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
    states_list = search_results_json.keys() | airtable_results_json.keys()

    for state in states_list:
        states[state] = dict()
        state_dict = airtable_results_json.get(state)
        if state_dict is None: continue
        for category in airtable_map:
            states[state][category] = dict()
            for subcategory in airtable_map[category]:
                states[state][category][subcategory] = dict()
                state_result_dict = states[state][category][subcategory] 
                
                if state_dict[subcategory] != '':
                    if state_dict[subcategory] == 'checked':
                        state_result_dict['value'] = True
                    else:
                        state_result_dict['value'] = parse_input(state_dict[subcategory])
                        if (len(state_result_dict['value']) == 1 and
                            'blank' in state_result_dict['value']):
                            state_result_dict['value'] = state_result_dict['value']['blank']

                if airtable_map[category][subcategory].get('Subsubcategories') is None: continue
                subsubcategories = airtable_map[category][subcategory]['Subsubcategories']

                if ("Source" in subsubcategories and state_dict[subsubcategories["Source"]] != ""):
                    state_result_dict["AirtableSource"] = parse_input(state_dict[subsubcategories["Source"]])
#                    print(category, subcategory)
#                    split_string(state_result_dict["AirtableSource"])

                if ("Other" in subsubcategories and state_dict[subsubcategories["Other"]] != ""):
                    state_result_dict["AirtableOther"] = parse_input(state_dict[subsubcategories["Other"]])
#                    if state_result_dict["AirtableOther"] == "":
#                        del state_result_dict["Airtable_source"] 


#                for val in airtable_map[category][subcategory]:
#                    #                    if state_dict[airtable_map[category][subcategory][val]]
#
#                    state_result_dict[val] = state_dict[airtable_map[category][subcategory][val]]

#        for val in states[state]:
#            print(f'{val} - {states[state][val]}')
#        print(states[state])
#    pprint.pp(states['Colorado'], width=180)
    with open("/tmp/airtable.json", 'w') as file:
        json.dump(states, file, indent=1)

URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+',
    re.IGNORECASE,
)

class ExtractedBlock:
    def __init__(self, block: str):
        self.title = None
        self.block = block
        blockList = []
        self.url = self.extractUrl()
        
        self.id = None
        self.val = None

    def addto(self, addto_dict):
        addto_dict[self.id] = {'value' : self.val, 'url' : self.url}

    def extract(self):
        self.extractFromTitle()
        if self.url:
            if len(self.url) == 1:
                self.val = self.cleanAnalysis(self.block.replace(self.url[0], ''))
            else:
                self.val = self.block
                for url in self.url:
                    self.val = self.val.replace(url, '')
                self.val = self.cleanAnalysis(self.val)

        if self.id is None and self.url:
            self.id = self.url[0] if len(self.url) == 1 else 'multiple_links'
            return True
        
        self.id = 'blank'
        self.val = self.block
        return False

    def extractFromTitle(self):
        lines = [line.strip() for line in self.block.splitlines() if line.strip()]

        if not lines:
            return None

        first = lines[0]

        if first.endswith(":"):
            self.id = self.title = first[:-1].strip()
            self.val = self.cleanAnalysis(self.block.replace(first, ''))
            return True
        return False

    def extractUrl(self):
        #         url = URL_PATTERN.search(self.block)
        url = URL_PATTERN.findall(self.block)
#        if url:
#            return url.group(0).strip().rstrip('",.)')
#        return None
        return url

    @staticmethod
    def cleanAnalysis(text: str) -> str:
        return text.strip()

    @staticmethod
    def mergeBlocks(blocks: list) -> dict:
        merged_blocks = dict() 
        merge_start = 0
        merged_blocks['blank'] = []
        for i in range(len(blocks)):
            if blocks[i].title:
                merged_blocks['blank'] += [block.val for block in blocks[merge_start:i]]
                merge_start = i + 1
            elif blocks[i].id != 'blank':
                ExtractedBlock.mergeAddTo(blocks[merge_start:i+1], merged_blocks)
                merge_start = i

        if blocks[-1].id == 'blank':
            merged_blocks['blank'] += [block.val for block in blocks[merge_start:]]
        if merged_blocks['blank'] == []:
            merged_blocks.pop('blank')

        return merged_blocks

    @staticmethod
    def mergeAddTo(blocks, addto_dict):
        block = blocks[0]
        for next_block in blocks[1:]:
            block.val += next_block.val
            block.url = next_block.url
            block.id = next_block.id

        block.addto(addto_dict)

def clean_analysis(block: str) -> str:
#    text = URL_PATTERN.sub("", text)
    return text.strip()


def parse_input(text: str) -> dict:
#    return text
    result = {}
    result_list = []
    blank = []

    blocks = re.split(r"\n\s*\n+", text)

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        extracted_block = ExtractedBlock(block)
        extracted_block.extract()
        result_list.append(extracted_block)
#        if extracted_block.extract():
#            result_list.append(extracted_block)
#            extracted_block.addto(result)
#        else:
#            blank.append(block)

#        if title:
#            result[title] = analysis
#
#        elif url:
#            result[url] = analysis
#
#        else:
#            blank.append(analysis)
    result = ExtractedBlock.mergeBlocks(result_list)
    print(result)


#    if blank:
#        result["blank"] = blank

    return result
#    return airtable_map


# dump_airtable_results()
map_to_questions()
