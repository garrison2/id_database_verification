#!/usr/bin/env python
import os, time

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


