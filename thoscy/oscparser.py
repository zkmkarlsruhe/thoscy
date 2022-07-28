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

# validates osc message, returns address components as a list or None on failure
# ex: "/foo/bar" -> ["foo", "bar"], "/" -> None, "abc123" -> None
def osc_validate(address, args):
    # check address
    if(address[0] != "/"):
        print(f"invalid osc address: {address}")
        return None
    components = address.split("/")
    if(len(components) < 2 or components[-1] == ""):
        print(f"invalid osc address: {address}")
        return None
    # check args
    if len(args) < 1:
        print(f"{address}: arguments are required")
        return None
    if components[-1] == "telemetry": # key/value pairs
        if len(args) < 2:
            print(f"{address}: min of 2 arguments is required")
            return None
        if len(args) % 2 != 0:
            print(f"{address}: arguments must come in key/value pairs")
            return None
    return components[1:] # drop leading "/"

# parse an OSC message into a ThingsBoard key/value JSON payload for MQTT
# address as a str, arguments as a list
#
# single values: "/value 123" -> {"value": 123}
#      or
# multiple values: "/value 1 2 3 4" -> {"value": [1, 2, 3, 4]}
#      or
# multiple key/value pairs:
# "/telemetry value1 123 value2 456" -> {"value1": 123, "value2": 456}
#
# compound addresses will be converted to nested objects:
#
# "/some/value 123" -> {"some": {"value": 123}}
#
# examples:
#   /hello world       -> {"hello": "world"}
#   /foo/bar 123       -> {"foo": {"bar": 123}}
#   /bar/baz abc 123   -> {"bar": {"baz": ["abc", 123]}}
#   /foo/telemetry bar 123 baz 456 -> {"foo": {"bar": 123, "baz": 456}}
#   /baz 1 2 3 4       -> {"baz": [1, 2, 3, 4]}
#
# returns json data on success or None on failure
def osc_to_json(address, args):

    # parse address components into keys
    keys = osc_validate(address, args)
    if keys == None: return None

    # walk through nested keys and set value(s) at end
    data = {} # json payload
    current = data
    for key in keys:
        if key == keys[-1]: # end of message, set value(s)
            if key == "telemetry": # key/value pairs
                for a in range(0, len(args), 2):
                    if type(args[0]) != str:
                        print(f"{address}: arg pair key must be a string, skipping {args[a]} {args[a+1]}")
                        continue
                    current[args[a]] = args[a+1]
            else: # single key with value
                current[key] = args[0] if len(args) == 1 else args
        else: # nest json object
            current[key] = {}
            current = current[key]
    if len(data) == 0: # nothing to send?
        return None
    return data

# commandline test
# example usage: ./oscparser.py /foo/bar 123
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("usage: OSCADDR ARGS...")
        sys.exit(0)
    address = sys.argv[1]
    args = [] # convert numbers from strings
    for arg in sys.argv[2:]:
        try: a = float(arg)
        except: a = arg
        args.append(a)
    data = osc_to_json(address, args)
    if data == None: sys.exit(1)
    print(data)
