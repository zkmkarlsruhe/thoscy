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
# * https://thingsboard.io/docs/reference/python-client-sdk/
# * https://github.com/attwad/python-osc

import asyncio
import signal
import argparse
import sys

from pythonosc.udp_client import SimpleUDPClient
from pythonosc import osc_bundle_builder
from pythonosc import osc_message_builder
from TBReceiver import TBReceiver
from threading import Thread

##### parser

parser = argparse.ArgumentParser(description="OSC <- Thingsboard websocket relay server")
parser.add_argument(
    "host", type=str, nargs="?", metavar="HOST",
    default="", help="ThingsBoard server host name, ie. board.mydomain.com")
parser.add_argument(
    "id", type=str, nargs="?", metavar="ID",
    default="", help="ThingsBoard device id")
parser.add_argument(
    "user", type=str, nargs="?", metavar="USER",
    default="", help="ThingsBoard user name")
parser.add_argument(
    "password", type=str, nargs="?", metavar="PASS",
    default="", help="ThingsBoard user password")
parser.add_argument(
    "-a", "--address", action="store", dest="addr",
    default="127.0.0.1", help="osc send address, default: 127.0.0.1")
parser.add_argument(
    "-p", "--port", action="store", dest="port",
    default=7788, type=int, help="osc send port, default: 7788")
parser.add_argument(
    "-t", "--telemetry", action="store_true", dest="telemetry",
    help="send all key/value pairs in a single /telemetry message")
parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
    help="enable verbose printing")
# TODO: accept user/pass via env vars and/or file?

##### thingsboard

# telemetry callback, sends key/value pairs as osc messages
# note: tries to convert values to float, ignores json keys for now
def received_telemetry(data):
    data_entry = data["data"]
    if data_entry == None:
        logger.error("telemetry data empty, are you allowed access to the device?")
        return
    if data["errorCode"] != 0:
        logger.warning(f"telemetry error: {data['errorCode']} {data['errorMsg']}")
        return
    #if args.verbose:
    #    print(f"received telemetry: {data}")
    if args.telemetry:
        # send multiple values:
        # {"value1": 123, "value2": 456} -> "/telemetry value1 123 value2 456"
        message = osc_message_builder.OscMessageBuilder(address="/telemetry")
        if args.verbose: print("/telemetry", end="")
        for key in data_entry.keys():
            if key == "json": continue
            value = data_entry[key][0][1]
            try:
                value = float(value)
            except:
                pass
            message.add_arg(key)
            message.add_arg(value)
            if args.verbose: print(f" {key}: {value}", end="")
        sender.send(message.build())
        if args.verbose: print("")
    else:
        # send single values: {"value": 123} -> "/value 123"
        # combines multiple message into a bundle
        bundle = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
        for key in data_entry.keys():
            if key == "json": continue
            value = data_entry[key][0][1]
            try:
                value = float(value)
            except:
                pass
            message = osc_message_builder.OscMessageBuilder(address="/"+key)
            message.add_arg(value)
            bundle.add_content(message.build())
            if args.verbose: print(f"{key}: {value}")
        sender.send(bundle.build())

##### main

# parse
args = parser.parse_args()
if args.host == "" or args.id == "" or args.user == "" or args.password == "":
    print("host, device id, user, & password required")
    sys.exit(1)

# osc sender
sender = SimpleUDPClient(args.addr, args.port)

# connect to ThingsBoard & subscribe to device telemetry
subscription_cmd = {
    "tsSubCmds": [
        {
            "entityType": "DEVICE",
            "entityId": args.id,
            "scope": "LATEST_TELEMETRY",
            "cmdId": 10
        }
    ],
    "historyCmds": [],
    "attrSubCmds": []
}
receiver = TBReceiver(subscription_cmd=subscription_cmd, callback=received_telemetry, **vars(args))
thread = Thread(target=TBReceiver.run_receiver, args=(0, receiver), daemon=False)
thread.start()

print(f"osc {args.addr}:{args.port} <- ws {args.host}")

try:
    thread.join()
except KeyboardInterrupt:
    pass
