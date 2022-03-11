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
import time
import sys

from tb_device_mqtt import TBDeviceMqttClient, TBPublishInfo
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

verbose = False

##### parser

parser = argparse.ArgumentParser(description="OSC -> Thingsboard MQTT relay server")
parser.add_argument(
    "host", type=str, nargs="?", metavar="HOST",
    default="", help="ThingsBoard server host name, ie. board.mydomain.com")
parser.add_argument(
    "token", type=str, nargs="?", metavar="TOKEN",
    default="", help="ThingsBoard device access token")
parser.add_argument(
    "-a", "--address", action="store", dest="addr",
    default="127.0.0.1", help="osc receive address, default: 127.0.0.1")
parser.add_argument(
    "-p", "--port", action="store", dest="port",
    default=7777, type=int, help="osc receive port, default: 7777")
parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
    help="enable verbose printing")

##### osc

# send single values: "/some/value 123" -> {"value": 123}
def received_osc(address, *args):
    if len(args) < 1:
        print("ignoring short message")
        return
    telemetry = {address.split("/")[-1]: args[0]}
    thingsboard.send_telemetry(telemetry)
    if verbose:
        print(f"{address} {args} -> {telemetry}")

# send multiple values:
# "/telemetry value1 123 value2 456" -> {"value1": 123, "value2": 456}
def received_telemetry(address, *args):
    if len(args) < 2:
        print(f"{address}: min of 2 arguments is required")
        return
    if len(args) % 2 != 0:
        print(f"{address}: arguments must come in key/value pairs")
        return
    telemetry = {}
    for a in range(0, len(args), 2):
        if type(args[0]) != str:
            print(f"{address}: arg pair key must be a string, skipping {args[a]} {args[a+1]}")
            return
        telemetry[args[a]] = args[a+1]
    thingsboard.send_telemetry(telemetry)
    if verbose:
        print(f"{address} {args} -> {telemetry}")

##### signal

# signal handler for nice exit
def sigint_handler():
    asyncio.get_running_loop().stop()

##### main

# signal handling
loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGINT, sigint_handler)

# parse
args = parser.parse_args()
print(f"osc {args.addr}:{args.port} -> mqtt {args.host}")
if args.verbose:
    verbose = True

# connect to thingsboard
thingsboard = TBDeviceMqttClient(args.host, args.token)
try:
    thingsboard.connect()
except Exception as exc:
    print(f"could not connect to thingsboard at {args.host}: {exc}")
    sys.exit(1)

# start osc server
dispatcher = Dispatcher()
dispatcher.set_default_handler(received_osc)
dispatcher.map("/telemetry", received_telemetry)
server = AsyncIOOSCUDPServer((args.addr, args.port), dispatcher, loop)
loop.run_until_complete(server.create_serve_endpoint())

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    thingsboard.disconnect()
