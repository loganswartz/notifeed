#!/usr/bin/env python3

import pathlib
import json
import time

def init_config(path: pathlib.Path):
    config = {'config':{'update_interval':15}, 'feeds':{}}
    with open(path, 'w') as file:
        json.dump(config, file)


def load_config(path: pathlib.Path):
    with open(path) as file:
        config = json.load(file)

    # reconvert latest_post_time time data back to struct_time object
    for entry in config['feeds'].keys():
        entry['latest_post_time'] = time.struct_time(entry['latest_post_time'])

    return config


def save_config(path: pathlib.Path, config: dict):
    with open(path, 'w') as file:
        json.dump(config, file)

