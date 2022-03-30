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

import asyncio
import sys

# websocket comm
import websockets
import socket
import json

# jwt token handling
import requests
import jwt

import logging
logger = logging.getLogger(__name__)

# ThingsBoard WebSocket receiver
# based on WSClient by Pietro Grandinetti:
# https://gist.github.com/pgrandinetti/964747a9f2464e576b8c6725da12c1eb
class TBReceiver: 

    # init with:
    # * host: ThingsBoard server hostname, ie. thingsboard.mydomain.com
    # * user credentials: username & password
    # * subscription command: subscription command JSON payload to receive specific telemetry updates,
    #   see WebSocket API section at https://thingsboard.io/docs/user-guide/telemetry/
    # * callback function: called when a subscription update is received,
    #   format: function(data) where data is a dictionary containing the message payload
    def __init__(self, host, user, password, subscription_cmd, callback, **kwargs):
        # required
        self.host = host
        self.subscription_cmd = subscription_cmd
        self.callback = callback
        self.user = user
        self.password = password
        # optional
        self.reply_timeout = kwargs.get("reply_timeout") or 10
        self.ping_timeout = kwargs.get("ping_timeout") or 5
        self.sleep_time = kwargs.get("sleep_time") or 5

    # connect to server and receive telemtery events,
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
                                logger.debug(f"ping error, retrying connection in {self.sleep_time} s")
                                await asyncio.sleep(self.sleep_time)
                                break
                        logger.debug(f"server said > {reply}")
                        if self.callback:
                            self.callback(json.loads(reply))
            except socket.gaierror:
                logger.debug("socket error, retrying connection in {self.sleep_time} s")
                await asyncio.sleep(self.sleep_time)
                continue
            except ConnectionRefusedError:
                logger.debug("connection refused, check host?")
                logger.debug("retrying connection in {self.sleep_time} s")
                await asyncio.sleep(self.sleep_time)
                continue

    # async thread run helper
    # example usage:
    #   thread = threading.Thread(target=TBReceiver.run, args=(0, receiver), daemon=False)
    #   thread.start()
    #   thread.join()
    @staticmethod
    def run_receiver(_, client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(client.listen_forever())

    # fetch user JWT tokens from a ThingsBoard host via the REST API
    # https://thingsboard.io/docs/reference/rest-api/
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

##### main

# test program to connect & print received telemetry messages
# exanple usage: python3 TBReceiver.py thingsboard.mydomain.com DEVICE_TOKEN tenant@mydomain.com PASSWORD
if __name__ == '__main__':
    from threading import Thread
    import argparse

    # telemetry callback
    def received_telemetry(data):
        data_entry = data["data"]
        if data_entry == None:
            print("data empty, are you allowed access to the device?")
            return
        if data["errorCode"] != 0:
            print(f"telemetry error: {data['errorCode']} {data['errorMsg']}")
            return
        print(data)
        for key in data_entry.keys():
            if key == "json": continue
            print(f"{key}: {data_entry[key][0][1]}")
    
    # parser
    parser = argparse.ArgumentParser(description="ThingsBoard websocket receiver test")
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
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
        help="enable verbose printing")
    args = parser.parse_args()
    if args.host == "" or args.id == "" or args.user == "" or args.password == "":
        print("host, device id, user, & password required")
        sys.exit(1)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # connect & subscribe to device telemetry
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

    try:
        thread.join()
    except KeyboardInterrupt:
        pass
