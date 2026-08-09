#!/usr/bin/env python
import os, time, shutil, textwrap

TERMINAL_WIDTH = shutil.get_terminal_size().columns
TABSIZE = 8

def get_most_recent_rdirs(results_path):
    convert = lambda t: time.mktime(time.strptime(t, "%d-%m-%Y_%H:%M:%S"))
    
    states = dict()
    print(results_path)
    for rdir in os.listdir(results_path):
        state = rdir[:rdir.find('_')]
        tval = convert(rdir[rdir.find('_') + 1:])
        if tval > states.get(state, (0, None))[0]:
            states[state] = (tval, rdir)

    results = []
    for state in states:
        results.append(states[state][1])

    results.sort()
    return results

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


