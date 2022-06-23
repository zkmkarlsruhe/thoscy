#! /usr/bin/env python3
#
# Copyright (c) 2022 ZKM | Hertz-Lab
# Dan Wilcox <dan.wilcox@zkm.de>
#
# BSD Simplified License.
# For information on usage and redistribution, and for a DISCLAIMER OF ALL
# WARRANTIES, see the file, "LICENSE.txt," in this distribution.
#
# This code has been developed at ZKM | Hertz-Lab as part of „The Intelligent
# Museum“ generously funded by the German Federal Cultural Foundation.

import json

# parse a ThingsBoard key/value JSON payload into an OSC message
# json data as a dictionary
#
# single values: {"value": 123} -> "/value 123"
#      or
# multiple values:
# {"value1": 123, "value2": 456} -> "/telemetry value1 123 value2 456"
#
# examples:
#   {"hello": "world"}                -> /hello world
#   {"foo": {"bar": 123}}             -> /foo/bar 123
#   {"bar": {"baz": ["abc", 123]}}    -> /bar/baz abc 123
#   {"foo": {"bar": 123, "baz": 456}} -> /foo/telemetry bar 123 baz 456
#
# returns (address, args) tuple on success or (None,None) on failure
def json_to_osc(data):
    print(data)
    if len(data) == 0:
        print("json empty")
        return (None, None)

    # collect address components from nested json keys
    components = []
    current = data
    while True: # follow first object(s) to lowest level
        foundobj = False
        for key,value in current.items():
            if isinstance(value, dict):
                # step into nested json object
                components.append(key)
                current = value
                foundobj = True
                break
        if not foundobj: break

    # parse key/value pairs
    args = []
    if len(current) == 1: # single pair
        for key,value in current.items():
            try:
                value = float(value)
            except:
                pass
            components.append(key)
            args = value
            break
    else: # multiple k/v pair /telemetry message
        components.append("telemetry")
        for key,value in current.items():
            if isinstance(value, list):
                print(f"skipping list in multiple key/value pair message: {key} {value}")
                continue
            try:
                value = float(value)
            except:
                pass
            args.append(key)
            args.append(value)
    address = "/" + "/".join(components)
    return (address,args)

# commandline test
# example usage: ./jsonparser.py '{"foo": {"bar": 123}}'
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("usage: JSON")
        sys.exit(1)
    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print(f"invalid json: {exc}")
        sys.exit(1)
    address,args = json_to_osc(data)
    if address == None: sys.exit(1)
    print(f"{address} {args}")
