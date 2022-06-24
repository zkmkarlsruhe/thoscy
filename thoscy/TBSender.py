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

import time

# thingsboard comm
from tb_device_mqtt import TBDeviceMqttClient
from tb_gateway_mqtt import TBGatewayMqttClient

import logging
logger = logging.getLogger(__name__)

# ThingsBoard MQTT sender wrapper
class TBSender:

    # init with
    # * host: ThingsBoard server hostname, ie. thingsboard.mydomain.com
    # * token: device token
    # additonal options:
    # * values_stringified: bool, store complex JSON values as strings?
    # * gateway: bool, device is a gateway
    # * gateway_devices: str array, device names (as displayed in the Thingsboard UI)
    def __init__(self, host, token, **kwargs):
        # optional
        self.gateway = kwargs.get("gateway") or False
        self.values_stringified = kwargs.get("values_stringified") or True
        # create client
        if self.gateway: # multiple device gateway client
            self.thingsboard = TBGatewayMqttClient(host, token)
            self.gateway_devices = kwargs.get("gateway_devices") or []
            if len(self.gateway_devices) == 0:
                logger.warning("using gateway, but not gateway devices given")
        else: # single device client
            self.thingsboard = TBDeviceMqttClient(host, token)
        #self.thingsboard.max_inflight_messages_set(100) # set this?

    # connect to server, returns True on success
    def connect(self):
        try:
            self.thingsboard.connect()
            if self.gateway:
                for device in self.gateway_devices:
                    self.thingsboard.gw_connect_device(device)
        except Exception as exc:
            logger.error(f"could not connect to thingsboard: {exc}")
            return False
        return True

    # disconnect from server
    def disconnect(self):
        if self.gateway:
            for device in self.gateway_devices:
                self.thingsboard.gw_disconnect_device(device)
        self.thingsboard.disconnect()

    # send telemetry JSON payload
    # when sending to a gateway, set the gateway_device as either:
    # * an int: self.gateway_devices index, or
    # * a str: device name string (as displayed in the Thingsboard UI)
    # returns True on success
    def send_telemetry(self, data, gateway_device=None):
        if data == None: return False
        if self.values_stringified:
           data = TBSender.stringify_values(data)
        try:
            if self.gateway:
                name = None
                if isinstance(gateway_device, str):
                    name = gateway_device 
                elif isinstance(gateway_device, int) and \
                   gateway_device < len(self.gateway_devices):
                    name = self.gateway_devices[gateway_device]
                if name == None:
                    logger.warning(f"send failed: gateway device not found: {gateway_device}")
                    return False
                # FIXME
                # It seems that gw_send_telemetry() expects both "ts" *and* "values" keys.
                # Sending only the "values" key results in setting "values": data in the device
                # telemetry instead of unpacking the key/values pairs in data. We provide a
                # self-computed "ts" timestamp for now. Tested with ThingsBoard v.3.3.4.1.
                self.thingsboard.gw_send_telemetry(name, {"ts": int(round(time.time() * 1000)), "values": data})
                logger.debug(f"sent to \"{name}\": {data}")
            else:
                # send_telemetry() doesn't need a "ts" key
                self.thingsboard.send_telemetry(data)
                logger.debug(f"sent: {data}")
        except Exception as exc:
            logger.error(f"send failed: {exc}")
            return False
        return True

    # stringify JSON object or array values
    @staticmethod
    def stringify_values(data):
        for key in data:
            value = data[key]
            if isinstance(value, dict) or isinstance(value, list):
                value = json.dumps(value, separators=(',', ':'))
                data[key] = value
                logger.debug(f"stringified {key}: {value}")
        return data

    # set log level
    @staticmethod
    def set_verbose(verbose):
        logging.basicConfig(level=(logging.DEBUG if verbose else logging.INFO))

##### main

# test program to send a telemetry message JSON payload
# example usage: python3 thoscy/TBSender.py thingsboard.mydomain.com TOKEN '{"foo": 123}'
# note: requires running in venv -> . ./venv/bin/activate
if __name__ == '__main__':
    import sys
    import argparse
    import json

    # parser
    parser = argparse.ArgumentParser(description="ThingsBoard MQTT sender test")
    parser.add_argument(
        "host", type=str, nargs="?", metavar="HOST",
        default="", help="ThingsBoard server host name, ie. thingsboard.mydomain.com")
    parser.add_argument(
        "token", type=str, nargs="?", metavar="TOKEN",
        default="", help="ThingsBoard device access token")
    parser.add_argument(
        "json", type=str, nargs="?", metavar="JSON",
        default="", help="JSON payload, ex. '{\"foo\": \"bar\"}'")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
        help="enable verbose printing")
    args = parser.parse_args()
    if args.host == "" or args.token == "" or args.json == "":
        print("host, device access token, & json payload required")
        sys.exit(1)
    if args.verbose: TBSender.set_verbose(True)

    # send json
    try:
        data = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(f"invalid json: {exc}")
        sys.exit(1)
    sender = TBSender(args.host, args.token)
    if sender.connect():
        if sender.send_telemetry(data):
            print(f"sent: {data}")
        sender.disconnect()
