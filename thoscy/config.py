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

host = ""
user = ""
password = ""

devices = {}

send = {
	"address": "127.0.0.1",
	"port": 7777,
	"devices": [],
	"telemetry": False
}

recv = {
	"address": "127.0.0.1",
	"port": 7788,
	"devices": [],
	"telemetry": False
}

verbose = False

def load_args(config, args):
	if args["host"] != None: config["host"] = 
	return config

def load_file(config, path):

