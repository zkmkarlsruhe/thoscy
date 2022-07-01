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
import sys
import os
import re

from pythonosc.udp_client import SimpleUDPClient
from pythonosc import osc_bundle_builder
from pythonosc import osc_message_builder
from threading import Thread

import thoscy
import json

##### parser

parser = argparse.ArgumentParser(description="OSC <- ThingsBoard websocket relay server")
parser.add_argument(
    "host", type=str, nargs="?", metavar="HOST",
    default="", help="ThingsBoard server host name, ie. thingsboard.mydomain.com")
parser.add_argument(
    "ids", type=str, nargs="*", metavar="ID",
    default="", help="ThingsBoard device id(s)")
parser.add_argument(
    "--user", action="store", dest="user",
    default="", help="ThingsBoard user name")
parser.add_argument(
    "--password", action="store", dest="password",
    default="", help="ThingsBoard user password")
parser.add_argument(
    "-a", "--address", action="store", dest="address",
    default="", help="OSC send address, default: 127.0.0.1")
parser.add_argument(
    "-p", "--port", action="store", dest="port",
    default=-1, type=int, help="OSC send port, default: 7788")
parser.add_argument(
    "-t", "--telemetry", action="store_true", dest="telemetry",
    help="send all key/value pairs in a single /telemetry message")
parser.add_argument(
    "--prefix", action="store_true", dest="prefix",
    help="force OSC address device name prefix for single device")
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
        self.user = ""
        self.password = ""
        self.ids = [] # device ids to subscribe to
        self.address = "127.0.0.1"
        self.port = 7788
        self.telemetry = False
        self.prefix = False # force OSC address device name prefix?
        self.verbose = False

        # subscribed device array of dicts, keys are:
        # * name: device name as shown in ThingsBoard UI
        # * key: device name as OSC address key prefix
        self.devices = []

    # load config from env vars, optional file, and commandline arguments
    def load(self, args):
        self._load_env()
        if args.file != "":
            if not self._load_file(args.file):
                return False
        self._load_args(args)
        return self._validate()

    # add device name to known devices by OSC address key prefix,
    # key will be stripped on non alphanumeric chars and made lowercase
    def add_device(self, key, name):
        key = re.sub("[\W_]+", "", key).lower()
        for device in self.devices:
            if key == device["key"]:
                print(f"ignoring duplicate device: {key} {name}")
                return
        self.devices.append({"key": key, "name": name})
        if len(self.devices) > 1: self.prefix = True

    # print current values
    def print(self):
        print(f"host: {self.host}")
        print(f"user: {self.user}")
        print(f"device id(s):")
        for device_id in self.ids:
            print(f"{device_id}")
        print(f"address: {self.address}")
        print(f"port: {self.port}")
        print(f"telemetry: {self.telemetry}")
        print(f"prefix: {self.prefix}")
        print(f"verbose: {self.verbose}")

    # print device OSC address key to name mappings
    def print_devices(self):
        if len(self.devices) > 0:
            print("device(s)")
            for device in self.devices:
                print(f"/{device['key']} <- {device['name']}")

    # load env vars
    def _load_env(self):
        # user credentials
        if "THOSCY_USER" in os.environ: self.user = os.environ.get("THOSCY_USER")
        if "THOSCY_PASS" in os.environ: self.password = os.environ.get("THOSCY_PASS")

    # load JSON file, returns True on success
    # TODO: check if key xists without throwing exception
    def _load_file(self, path):
        try:
            f = open(args.file)
            config = json.load(f)
            f.close()        
            if "host" in config.keys(): self.host = config["host"]
            if "user" in config.keys(): self.user = config["user"]
            if "password" in config.keys(): self.password = config["password"]
            if "verbose" in config.keys(): self.verbose = config["verbose"]
            if "recv" in config.keys():
                recv = config["recv"]
                if "address" in recv.keys(): self.address = recv["address"]
                if "port" in recv.keys(): self.port = recv["port"]
                if "telemetry" in recv.keys(): self.telemetry = recv["telemetry"]
                if "prefix" in recv.keys(): self.prefix = recv["prefix"]
                if "devices" in recv.keys() and len(recv["devices"]) > 0 and \
                   "devices" in config.keys() and len(config["devices"]) > 0:
                    for key in recv["devices"]:
                        if key not in config["devices"].keys():
                            print(f"ignoring unknown recv device: {key}")
                            continue
                        device = config["devices"][key]
                        if "id" not in device.keys() or device["id"] == "":
                           print(f"ignoring recv device without name: {key}")
                           continue
                        self.ids.append(device["id"])
        except Exception as exc:
            print(f"could not open or read {args.file}: {type(exc).__name__} {exc}")
            return False
        return True

    # load commandline args
    def _load_args(self, args):
        # override
        if args.host != "": self.host = args.host
        if args.user != "": self.user = args.user
        if args.password != "": self.password = args.password
        if args.address != "": self.address = args.address
        if args.port != -1: self.port = args.port
        if not self.telemetry and args.telemetry: self.telemetry = True
        if not self.prefix and args.prefix: self.prefix = True
        if not self.verbose and args.verbose: self.verbose = True
        # append
        for device in args.ids: self.ids.append(device)

    # validate current values, returns True on success
    def _validate(self):
        if self.host == "":
            print("host required")
            return False
        if len(self.ids) == 0:
            print("device id(s) required")
            return False
        # prompt for user and/or password?
        try:
            if self.user == "":
                self.user = input("user: ")
            if self.password == "":
                import getpass
                self.password = getpass.getpass("password: ")
        except:
            return False
        if self.user == "" or self.password == "":
            print("user & password required")
            return False
        return True

##### thingsboard

# device info callback, ignore if not using device name prefix
# FIXME: what to do if # devices does not match up with # config.devices?
#        in this case, the cmdId/subscriptionId indices could be wrong
def received_devices(devices):
    if len(config.devices) < 2 and not config.prefix: return
    for device in devices:
        name = device['name']
        config.add_device(name, name)
    if config.verbose: config.print_devices()

# telemetry callback, sends key/value pairs as osc messages
# note: tries to convert values to float, ignores json keys for now
def received_telemetry(data):
    data_entry = data["data"]
    if data_entry == None:
        if data["errorCode"] != 0:
            print(f"telemetry error {data['errorCode']}: {data['errorMsg']}")
        else:
            print("telemetry error: data empty, did connection fail?")
        return
    prefix = ""
    if config.prefix:
        # device name prefix?
        data_id = data["subscriptionId"]
        device = config.devices[data_id]
        if device == None or "key" not in device.keys() or device["key"] == "":
            print(f"telemetry warning: received update from unknown device: {data_entry.keys()}")
            return
        prefix = "/" + device["key"]
    if config.telemetry:
        # send multiple values:
        # {"value1": 123, "value2": 456} -> "/telemetry value1 123 value2 456"
        address = prefix + "/telemetry"
        message = osc_message_builder.OscMessageBuilder(address=address)
        if config.verbose: print(address, end="")
        for key in data_entry.keys():
            if key == "" or key == "json": continue
            value = data_entry[key][0][1]
            try:
                value = float(value)
            except:
                pass
            message.add_arg(key)
            message.add_arg(value)
            if config.verbose: print(f" {key}: {value}", end="")
        sender.send(message.build())
        if config.verbose: print("")
    else:
        # send single values: {"value": 123} -> "/value 123"
        # combines multiple message into a bundle
        bundle = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
        for key in data_entry.keys():
            if key == "" or key == "json": continue
            value = data_entry[key][0][1]
            try:
                value = float(value)
            except:
                pass
            address = prefix + "/" + key
            message = osc_message_builder.OscMessageBuilder(address=address)
            message.add_arg(value)
            bundle.add_content(message.build())
            if config.verbose:
                if prefix != "": print(f"{prefix} ", end="")
                print(f"{key}: {value}")
        sender.send(bundle.build())

##### main

# parse config
args = parser.parse_args()
config = Config()
if not config.load(args):
    sys.exit(1)
if args.verbose > 1:
    thoscy.TBReceiver.set_verbose(True)
args = None
parser = None
if config.verbose: config.print()

# osc sender
sender = SimpleUDPClient(config.address, config.port)

# connect & subscribe to device telemetry
# the cmdId key is returned as the subscriptionId key when receiving telemetry,
# in this case we use it as an index in the config.devices array
subscription_cmd = {"tsSubCmds": []}
cmd_id = 0
for device_id in config.ids:
    subscription_cmd["tsSubCmds"].append(
        {
            "entityType": "DEVICE",
            "entityId": device_id,
            "scope": "LATEST_TELEMETRY",
            "cmdId": cmd_id
        }
    )
    cmd_id = cmd_id + 1
receiver = thoscy.TBReceiver(subscription_cmd=subscription_cmd, \
                             telemetry_callback=received_telemetry, \
                             device_callback=received_devices, **vars(config))
thread = Thread(target=thoscy.TBReceiver.run_receiver, args=(0, receiver), daemon=False)
thread.start()

# wait for receiver to exit
print(f"osc {config.address}:{config.port} <- ws {config.host}")
try:
    thread.join()
except KeyboardInterrupt:
    pass
