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
# * https://thingsboard.io/docs/user-guide/telemetry/
# * https://thingsboard.io/docs/reference/rest-api/

import asyncio

# websocket comm
import websockets
import socket
import json

# REST API comm
import requests

import logging
logger = logging.getLogger(__name__)

# ThingsBoard WebSocket receiver
# based on WSClient by Pietro Grandinetti:
# https://gist.github.com/pgrandinetti/964747a9f2464e576b8c6725da12c1eb
class TBReceiver: 

    # init with
    # * host: str, ThingsBoard server hostname, ie. thingsboard.mydomain.com
    # * user credentials: str, username & password
    # * subscription command: dict, subscription command JSON payload to receive
    #   specific telemetry updates, see WebSocket API section at
    #   https://thingsboard.io/docs/user-guide/telemetry/
    # * telemetry_callback: function, called when a subscription update is received,
    #   format: function(data) where data is a dictionary containing the message payload
    # additional options:
    # * device_callback: function, called after initial connect,
    #   format: function(info) where info is a list of device dicts, one for each subscription 
    # * values_stringified: bool, are complex JSON values as stored as strings?
    # * reply_timeout: int seconds, subscription reply timeout
    # * ping_timeout: int seconds, length between keep alive pings
    # * sleep_time: int seconds, sleep between retrying connection on error
    def __init__(self, subscription_cmd, telemetry_callback, host, user, password, **kwargs):
        # required
        self.host = host
        self.user = user
        self.password = password
        self.subscription_cmd = subscription_cmd
        self.telemetry_callback = telemetry_callback
        # optional
        self.device_callback = kwargs.get("device_callback") or None
        self.values_stringified = kwargs.get("values_stringified") or True
        self.reply_timeout = kwargs.get("reply_timeout") or 10
        self.ping_timeout = kwargs.get("ping_timeout") or 5
        self.sleep_time = kwargs.get("sleep_time") or 5

    # connect to server and receive telemetry events,
    # attempts reconnection on failure
    async def listen_forever(self):
        while True:
            # outer loop restarted every time the connection fails
            logger.debug("creating new connection...")
            try:
               token, _ = TBReceiver.fetch_tokens(self.host, self.user, self.password)
               url = "wss://" + self.host + "/api/ws/plugins/telemetry?token=" + token
               async with websockets.connect(url) as ws:
                    # send the subscription
                    await ws.send(json.dumps(self.subscription_cmd))
                    # fetch device info?
                    if self.device_callback:
                        try:                    
                            device_ids = []
                            for sub in self.subscription_cmd["tsSubCmds"]:
                                if sub["entityType"] == "DEVICE":
                                    device_ids.append(sub["entityId"])
                            devices = TBReceiver.fetch_devices(self.host, token, device_ids)
                            if devices: self.device_callback(devices)
                        except Exception as exc:
                            logger.warning(f"fetching devices failed: {exc}")
                            pass
                    # listener loop
                    while True:
                        try:
                            reply = await asyncio.wait_for(ws.recv(), timeout=self.reply_timeout)
                        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                            try:
                                pong = await ws.ping()
                                await asyncio.wait_for(pong, timeout=self.ping_timeout)
                                logger.debug("ping ok, keeping connection alive...")
                                continue
                            except:
                                logger.error(f"ping error, retrying connection in {self.sleep_time} s")
                                await asyncio.sleep(self.sleep_time)
                                break
                        logger.debug(f"server said: {reply}")
                        data = json.loads(reply)
                        if self.values_stringified:
                            data["data"] = TBReceiver.parse_values(data["data"])
                        self.telemetry_callback(data)
            except socket.gaierror:
                logger.error(f"socket error, retrying connection in {self.sleep_time} s")
                await asyncio.sleep(self.sleep_time)
                continue
            except ConnectionRefusedError:
                logger.error("connection refused, check host?")
                logger.error(f"retrying connection in {self.sleep_time} s")
                await asyncio.sleep(self.sleep_time)
                continue
            except Exception as exc:
                logger.error("connection failed, check host?")
                logger.error(exc)
                break

    # async thread run helper
    # example usage:
    #   thread = threading.Thread(target=TBReceiver.run_receiver, args=(0, receiver), daemon=False)
    #   thread.start()
    #   thread.join()
    @staticmethod
    def run_receiver(_, client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.listen_forever())
        except:
            pass

    # fetch user JWT tokens from a ThingsBoard host via the REST API
    # returns token tuple (access, refresh) on success or None on failure
    @staticmethod
    def fetch_tokens(host, user, password):

        # exchange login credentials for login tokens
        url = "https://" + host + "/api/auth/login"
        header = {"Content-Type": "application/json", "Accept": "application/json"}
        data = {"username": user, "password": password}
        req = requests.post(url, headers=header, json=data)
        if req.status_code != 200:
            logger.error(f"requesting login tokens failed: {req.status_code} {req.json()['message']}")
            return None
        resp = req.json()
        access = resp["token"]
        refresh = resp["refreshToken"]

        # exchange login tokens for main tokens
        url = "https://" + host + "/api/auth/token"
        header = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Authorization": "Bearer " + access
        }
        data = {"refreshToken": refresh}
        req = requests.post(url, headers=header, json=data)
        if req.status_code != 200:
            logger.error(f"requesting main tokens failed: {req.status_code} {req.json()['message']}")
            return None
        resp = req.json()
        access = resp["token"]
        refresh = resp["refreshToken"]

        return access, refresh

    # fetch device info from device id(s) via the REST API
    # returns list of device dicts on success or None on failure
    @staticmethod
    def fetch_devices(host, access, ids):
        url = "http://" + host + "/api/devices?deviceIds=" + ",".join(ids)
        header = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Authorization": "Bearer " + access
        }
        req = requests.get(url, headers=header)
        if req.status_code != 200:
            logger.error(f"fetching device(s) failed: {req.status_code} {req.json()['message']}")
            return None
        return req.json()

    # parse stringified JSON object or array values in telemetry message
    @staticmethod
    def parse_values(data):
        for key in data:
            if key == "latestValues": continue
            value = data[key][0][1]
            if isinstance(value, str) and len(value) != 0 and \
                ((value[0] == '{' and value[-1] == '}') or \
                 (value[0] == '[' and value[-1] == ']')):
                try:
                    data[key][0][1] = json.loads(value)
                    logger.debug(f"parsed {key}: {value}")
                except json.JSONDecodeError as exc:
                    logger.debug(f"parse failed for {key}: {exc}")
                    pass
        return data

    # set log level
    @staticmethod
    def set_verbose(verbose):
        logging.basicConfig(level=(logging.DEBUG if verbose else logging.INFO))

##### main

# test program to connect & print received telemetry messages
# example usage: python3 thoscy/TBReceiver.py thingsboard.mydomain.com USERNAME PASSWORD ID
# note: requires running in venv -> . ./venv/bin/activate
if __name__ == '__main__':
    from threading import Thread
    import sys
    import argparse
    
    # parser
    parser = argparse.ArgumentParser(description="ThingsBoard websocket receiver test")
    parser.add_argument(
        "host", type=str, nargs="?", metavar="HOST",
        default="", help="ThingsBoard server host name, ie. thingsboard.mydomain.com")
    parser.add_argument(
        "user", type=str, nargs="?", metavar="USER",
        default="", help="ThingsBoard user name")
    parser.add_argument(
        "password", type=str, nargs="?", metavar="PASS",
        default="", help="ThingsBoard user password")
    parser.add_argument(
        "id", type=str, nargs="?", metavar="ID",
        default="", help="ThingsBoard device id")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
        help="enable verbose printing")
    args = parser.parse_args()
    if args.host == "" or args.id == "" or args.user == "" or args.password == "":
        print("host, user, password, & device id required")
        sys.exit(1)
    if args.verbose: TBReceiver.set_verbose(True)

    # device info callback
    def received_devices(devices):
        print(f"{len(devices)} device(s)")
        for device in devices:
            print(f"  {device['id']['id']} \"{device['name']}\"")

    # telemetry callback
    def received_telemetry(data):
        data_entry = data["data"]
        if data_entry == None:
            if data["errorCode"] != 0:
                print(f"telemetry error {data['errorCode']}: {data['errorMsg']}")
            else:
                print("telemetry error: data empty, did connection fail?")
            return
        print(data)
        for key in data_entry.keys():
            if key == "" or key == "json": continue
            print(f"{key}: {data_entry[key][0][1]}")

    # connect & subscribe to device telemetry
    subscription_cmd = {
        "tsSubCmds": [
            {
                "entityType": "DEVICE",
                "entityId": args.id,
                "scope": "LATEST_TELEMETRY",
                "cmdId": 10
            }
        ]
    }
    receiver = TBReceiver(subscription_cmd=subscription_cmd, \
                          telemetry_callback=received_telemetry, \
                          device_callback=received_devices, **vars(args))
    thread = Thread(target=TBReceiver.run_receiver, args=(0, receiver), daemon=False)
    thread.start()

    # wait for receiver to exit
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
