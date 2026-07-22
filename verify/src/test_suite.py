import os, time
import json
import subprocess
from os.path import join as joinpath

from constants import *

def dump_test(test_type, val):
    time_str = time.strftime("%d-%m-%Y-%H_%M_%S")
    os.makedirs(joinpath(TEST_DIR, test_type), exist_ok=True)
    filepath = joinpath(TEST_DIR, test_type, time_str)
    with open(filepath, 'w') as file:
        json.dump(val, file, indent=1)

def diff_latest(test_type):
    files = sorted(os.listdir(joinpath(TEST_DIR, test_type)), reverse=True)
    if len(files) >= 2:
        subprocess.run(["vimdiff", joinpath(TEST_DIR, test_type, files[0]), 
                        joinpath(TEST_DIR, test_type, files[1])])

def dump_and_diff(test_type, val):
    dump_test(test_type, val)
    diff_latest(test_type)
