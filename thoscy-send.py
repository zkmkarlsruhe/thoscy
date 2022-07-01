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
#
# References:
# * https://github.com/attwad/python-osc

import asyncio
import signal
import argparse
import time
import sys
import re

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

import thoscy
import json

##### parser

parser = argparse.ArgumentParser(description="OSC -> Thingsboard MQTT relay server")
parser.add_argument(
    "host", type=str, nargs="?", metavar="HOST",
    default="", help="ThingsBoard server host name, ie. thingsboard.mydomain.com")
parser.add_argument(
    "token", type=str, nargs="?", metavar="TOKEN",
    default="", help="ThingsBoard device access token, must be gateway device if providing additional names")
parser.add_argument(
    "names", type=str, nargs="*", metavar="NAME",
    default="", help="ThingsBoard device name(s), requires gateway device")
parser.add_argument(
    "-a", "--address", action="store", dest="address",
    default="", help="OSC receive address, default: 127.0.0.1")
parser.add_argument(
    "-p", "--port", action="store", dest="port",
    default=-1, type=int, help="OSC receive port, default: 7777")
parser.add_argument(
    "-f", "--file", action="store", dest="file",
    default="", help="JSON configuration file")
parser.add_argument("-v", "--verbose", action='count', dest="verbose",
    default=0, help="enable verbose printing, use -vv for debug verbosity")

##### config

# configuration values
class Config:

    def __init__(self):
        self.host = ""
        self.token = ""
        self.address = "127.0.0.1"
        self.port = 7777
        self.verbose = False

        # device names by OSC address key
        self.devices = {}

    # load config from env vars, optional file, and commandline arguments
    def load(self, args):
        if args.file != "":
            if not self._load_file(args.file):
                return False
        self._load_args(args)
        return self._validate()

    # add device name to known devices by OSC address key prefix,
    # key will be stripped on non alphanumeric chars and made lowercase
    def add_device(self, key, name):
        key = re.sub("[\W_]+", "", key).lower()
        if key in self.devices:
            print(f"ignoring duplicate device: {key} {name}")
        else:
            self.devices[key] = name

    # print current values
    def print(self):
        print(f"host: {self.host}")
        print(f"device token: {self.token}")
        print(f"address: {self.address}")
        print(f"port: {self.port}")
        print(f"verbose: {self.verbose}")

    # print device OSC address key to name mappings
    def print_devices(self):
        if len(self.devices) > 0:
            print("device(s)")
            for key in self.devices:
                print(f"  /{key} -> {self.devices[key]}")

    # load JSON file, returns True on success
    # TODO: check if key xists without throwing exception
    def _load_file(self, path):
        try:
            f = open(args.file)
            config = json.load(f)
            f.close()        
            if "host" in config.keys(): self.host = config["host"]
            if "verbose" in config.keys(): self.verbose = config["verbose"]
            if "send" in config.keys():
                send = config["send"]
                if "token" in send.keys(): self.token = send["token"]
                if "address" in send.keys(): self.address = send["address"]
                if "port" in send.keys(): self.port = send["port"]
                if "devices" in send.keys() and len(send["devices"]) > 0 and \
                    "devices" in config.keys() and len(config["devices"]) > 0:
                    for key in send["devices"]:
                        if key not in config["devices"].keys():
                            print(f"ignoring unknown send device: {key}")
                            continue
                        device = config["devices"][key]
                        if "name" not in device.keys() or device["name"] == "":
                            print(f"ignoring send device without name: {key}")
                            continue
                        name = device["name"]
                        self.add_device(name, name)
        except Exception as exc:
            print(f"could not open or read {args.file}: {type(exc).__name__} {exc}")
            return False
        return True

    # load commandline args
    def _load_args(self, args):
        # override
        if args.host != "": self.host = args.host
        if args.token != "": self.token = args.token
        if args.address != "": self.address = args.address
        if args.port != -1: self.port = args.port
        if not self.verbose and args.verbose: self.verbose = True
        # append
        for name in args.names: self.add_device(name, name)

    # validate current values, returns True on success
    def _validate(self):
        if self.host == "":
            print("host required")
            return False
        if self.token == "":
            print("device access token required")
            return False
        return True

##### osc

# send single values: "/some/value 123" -> {"value": 123}
def received_osc(address, *args):
    if config.verbose:
        print(f"{address} {args}")
    if sender.gateway:
        # using gateway: filter first address component as device name prefix
        components = address.split("/")
        if len(components) < 3: # need min of: / prefix / key
            print(f"invalid osc address: {address}")
            return
        prefix = components[1]
        try:
            name = config.devices[prefix]
        except:
            print(f"unknown device: {prefix}")
            return
        address = "/" + "/".join(components[2:])
        data = thoscy.osc_to_json(address, list(args))
        sender.send_telemetry(data, device_name=name)
    else:
        # single device
        data = thoscy.osc_to_json(address, list(args))
        sender.send_telemetry(data)

##### signal

# signal handler for nice exit
def sigint_handler():
    asyncio.get_running_loop().stop()

##### main

# signal handling
loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, sigint_handler)

# parse config
args = parser.parse_args()
config = Config()
if not config.load(args):
    sys.exit(1)
if args.verbose > 1:
    thoscy.TBSender.set_verbose(True)
args = None
parser = None
if config.verbose:
    config.print()
    config.print_devices()

# connect to thingsboard
sender = thoscy.TBSender(config.host, config.token, \
                         values_stringified=False,
                         gateway=(len(config.devices) > 0), \
                         gateway_devices=list(config.devices.values()))
if not sender.connect():
    sys.exit(1)

# start osc receiver
dispatcher = Dispatcher()
dispatcher.set_default_handler(received_osc)
receiver = AsyncIOOSCUDPServer((config.address, config.port), dispatcher, loop)
loop.run_until_complete(receiver.create_serve_endpoint())

# wait for osc receiver to exit
print(f"osc {config.address}:{config.port} -> mqtt {config.host}")
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    sender.disconnect()
