thoscy
======

![thoscy logo](media/icon.png)

_thoscy: **th**ingsboard **osc** rela**y**_

Relay messages between a ThingsBoard server and OSC.

This code base has been developed by [ZKM | Hertz-Lab](https://zkm.de/en/about-the-zkm/organization/hertz-lab) as part of the project [»The Intelligent Museum«](#the-intelligent-museum). 

Copyright (c) 2022 ZKM | Karlsruhe.  
Copyright (c) 2022 Dan Wilcox.  

BSD Simplified License.

Description
-----------

This set of scripts act as relay servers for forwarding device events between a ThingsBoard server using MQTT/WebSockets and OSC (Open Sound Control) messages. `thoscy-send` forwards messages from OSC to a ThingsBoard host over MQTT while `thoscy-recv` listens for ThingsBoard device events on a WebSocket and forwards them over OSC. This is useful for creative coding tools which work with OSC messages natively, but do not have built-in MQTT or WebSocket support.

From [thingsboard.io](https://thingsboard.io):

>ThingsBoard is an open-source IoT platform for data collection, processing, visualization, and device management.
>It enables device connectivity via industry standard IoT protocols - MQTT, CoAP and HTTP and supports both cloud and on-premises deployments. ThingsBoard combines scalability, fault-tolerance and performance so you will never lose your data.

From [opensoundcontrol.org](OpenSoundControl.org):

>OpenSoundControl (OSC) is a data transport specification (an encoding) for realtime message communication among applications and hardware.

Dependencies
------------

* Python 3
* [tb-mqtt-client](https://github.com/thingsboard/thingsboard-python-client-sdk)
* [python-osc](https://github.com/attwad/python-osc)
* [websockets](https://github.com/aaugustin/websockets)
* [requests](https://github.com/psf/requests)

Setup
-----

Install Python 3, if not already available. For instance, on macOS using [Homebrew](http://brew.sh):

```shell
brew install python3
```

Create a virtual environment and install the script's dependencies:

```shell
make
```

ThingsBoard
-----------

If starting with ThingsBoard from scratch, it's highly recommended to first consult the official ThingsBoard Community [Getting Started Guide](https://thingsboard.io/docs/getting-started-guides/helloworld/).

Otherwise, a _very basic_ overview follows.

### Creating a device

Basic steps for creating a device (as of Spring 2022):

1. Create an account & log into the ThingsBoard server
2. Click on Devices in the sidebar
3. In the Devices panel, click the + in the upper right and choose "Add new device"
4. Enter a name (such as "Test device", "Foo", etc) and click Add

Once a device is created, sending and receiving via the server host and device access token / id should be possible using the thoscy tools.

Additionally, to send to multiple devices from a single thoscy-send session, a gateway device is required. Follow the steps to create a new device as before, then:

5. (Optional) In the Devices panel, check "Is gateway" for the new gateway device

### Device access token and id

To find the device access token and id:

1. Log into the ThingsBoard server
2. Click on Devices in the sidebar
3. In the Devices panel, choose the device in the list
4. In the Device details, choose the Details tab
5. Click either the "Copy device id" or "Copy access token"
6. Paste text somewhere on your system, ie. in TexEdit, onto the console, etc

`thoscy-send` uses the device access token

`thoscy-recv` uses the device id 

### Watching device telemetry in realtime

To view the current device telemetry values in "realtime" without setting up a ThingsBoard Dashboard:

1. Log into the ThingsBoard server
2. Click on Devices in the sidebar
3. In the Devices panel, choose the device in the list
4. In the Device details, choose the Telemetry tab

_Note: This shows *all* received key/pair pairs, even those not currently in use._

Running
-------

Send and receive functionality is split into two separate scripts: `thoscy-send` and `thoscy-recv`.

### thoscy-send

~~~
usage: thoscy-send.py [-h] [-a ADDRESS] [-p PORT] [-f FILE] [-v] [HOST] [TOKEN] [NAME ...]

OSC -> Thingsboard MQTT relay server

positional arguments:
  HOST                  ThingsBoard server host name, ie. thingsboard.mydomain.com
  TOKEN                 ThingsBoard device access token, must be gateway device if providing additional names
  NAME                  ThingsBoard device name(s), requires gateway device

optional arguments:
  -h, --help            show this help message and exit
  -a ADDRESS, --address ADDRESS
                        OSC receive address, default: 127.0.0.1
  -p PORT, --port PORT  OSC receive port, default: 7777
  -f FILE, --file FILE  JSON configuration file
  -v, --verbose         enable verbose printing, use -vv for debug verbosity
~~~

Start an OSC send server on the commandline via the virtual environment wrapper script:

    ./thoscy-send HOST TOKEN

`HOST` is the ThingsBoard server host name, ie. thingsboard.mydomain.com.

`TOKEN` is the ThingsBoard device access token (not id).

`NAME` is a ThingsBoard device name string, multiple device names can be given (see section below)

To stop thoscy-send, use CTRL+C to issue an interrupt signal.

#### Sending

Once running, thoscy-send automatically parses OSC messages into telemetry messages to send to the device on ThingsBoard via MQTT. Message handling is as follows:

Send single values: `"/some/value 123" -> {"value": 123}`
* Last address component used as entity key
* First argument uses as entity value
* Message must contain at least one argument

Send multiple values: `"/telemetry value1 123 value2 456" -> {"value1": 123, "value2": 456}`
* Last address component `telemetry`
* Arguments are treated as entity key/value pairs
* Each argument key must be a string type
* Message must contain at least two arguments (key/value pair)

#### Multiple-Device Handling

thoscy-send can send to multiple devices through a single ThingsBoard gateway device. Start thoscy-send with the access token to the gateway, then provide one or more device names as shown in the ThingsBoard UI. For example:

    ./thoscy-send thingsboard.zkm.de ABcdeF... "device 1" "device 2"

_Note: Make sure to escape any names which include spaces by using double-quotes on the commandline._

The device names are used as the first component in the OSC address: `"/device1/value 123 -> {"value": 123} to "device 1"`
* OSC address must be prepended with the device name prefix
* Device names are made lowercase and stripped of non-alphanumeric chars, ie. "device 1" becomes "/device1"

Any device names which do not exist on the ThingsBoard server will automatically be created through the gateway.

### thosy-recv

~~~
usage: thoscy-recv.py [-h] [--user USER] [--password PASSWORD] [-a ADDRESS] [-p PORT] [-t] [-f FILE] [-v] [HOST] [ID ...]

OSC <- ThingsBoard websocket relay server

positional arguments:
  HOST                  ThingsBoard server host name, ie. thingsboard.mydomain.com
  ID                    ThingsBoard device id(s)

optional arguments:
  -h, --help            show this help message and exit
  --user USER           ThingsBoard user name
  --password PASSWORD   ThingsBoard user password
  -a ADDRESS, --address ADDRESS
                        OSC send address, default: 127.0.0.1
  -p PORT, --port PORT  OSC send port, default: 7788
  -t, --telemetry       send all key/value pairs in a single /telemetry message
  --prefix              force OSC address device name prefix for single device
  -f FILE, --file FILE  JSON configuration file
  -v, --verbose         enable verbose printing, use -vv for debug verbosity
~~~

Start an OSC receive server on the commandline via the virtual environment wrapper script:

    ./thoscy-recv HOST ID...

`HOST` is the ThingsBoard server host name, ie. thingsboard.mydomain.com

`ID` is a ThingsBoard device id (not access token), multiple device ids can be given (see section below)

To stop thoscy-recv, use CTRL+C to issue an interrupt signal.

#### Login Credentials

ThingsBoard account login credentials are required and can be given via the following (in order of precedence):
* the `THOSCY_USER` & `THOSCY_PASS` environment variables
* a JSON config file
* the `--user` and `--password` options

If the user or password are unset, thoscy-recv will ask for each on the commandline when it is run, ex:

~~~
% ./thoscy-recv --user user@mydomain.com thingsboard.mydomain.com e5a69b00-...
password:
~~~

The environment variables can be given either directly on the commandline:

    THOSCY_PASS=MYPASSWORD ./thoscy-recv --user user@mydomain.com thingsboard.mydomain.com e5a69b00-...

or via exporting into the current environment, ex. within a script:

```shell
#! /bin/sh
export THOSCY_USER=user@mydomain.com
export THOSCY_PASS=MYPASSWORD
thoscy-recv thingsboard.mydomain.com e5a69b00-...
```

_Note: neither user nor password are saved between thoscy-recv sessions._

#### Receiving

Once running, thoscy-recv automatically parses ThingsBoard device telemetry messsages received over a WebSocket into OSC messages. Message handling is as follows:

Receive single values: `{"value": 123} -> "/value 123"`
* Key/value pairs sent in individual OSC messages
* Entity key used as address component
* JSON key/value pairs are ignored

Receive multiple values: `{"value1": 123, "value2": 456} -> "/telemetry value1 123 value2 456"`
* Key/value pairs sent in a OSC single message
* Key/value pairs appended as arguments
* Value types: string or float
* JSON key/value pairs are ignored

_Note: Forwarding telemetry messages as a `/telemetry` OSC message with multiple values requires using the `-t/--telemetry` commandline option or JSON config "telemetry" key._

#### Multiple-Device Handling

When starting thoscy-recv with multiple device ids, the device names are fetched from the server and used as the first component in the OSC address: `{"value": 123} from "device 1" -> "/device1/value 123"`
* OSC address is prepended with the device name prefix
* Device names are made lowercase and stripped of non-alphanumeric chars, ie. "device 1" becomes "/device1"

_Note: When starting thoscy-recv with a **single device**, the device prefix is not used by default. This behavior can be changed via the `--prefix` commandline option or JSON config "prefix" key._

### JSON config file

Configuration variables can be given to either thoscy tool via a JSON file which consists of a dictionary with the following keys/values:

* **host**: _string_, ThingsBoard server host name, ie. thingsboard.mydomain.com
* **user**: _string_, ThingsBoard user name (receiving)
* **password**: _string_, ThingsBoard user password (receiving)
* **verbose**: _bool_, enable verbose printing?
* **devices**: _dict_, device info dicts by keyname 
  - **name**: _string_, device name as shown in the ThingsBoard UI
  - **id**: _string_, ThingsBoard device id
* **send**: _dict_, send-specific values
  - **address**: _string_, OSC receive address
  - **port**: _int_, OSC receive port (>1024)
  - **token**: _string_, ThingsBoard device access token
  - **devices**: _array_, devices to send to by keyname in the main devices dict
* **receive**: _dict_, receive-specific values
  - **address**: _string_, OSC send address
  - **port**: _int_, OSC send port (>1024)
  - **telemetry**: _bool_, send key/value pairs in single /telemetry message
  - **prefix**: _bool_, force OSC address device name prefix for single device
  - **devices**: _array_, devices to receive from by keyname in the main devices dict

_Note: Values are be overridden when the corresponding commandline option is used._

Simple example:

```json
{
    "host": "thingsboard.mydomain.com",
    "devices": {
        "dev1": {"name": "device 1", "id": "12345-..."},
        "dev2": {"name": "device 2", "id:": "67890-..."}
    },
    "send": {
        "token": "ABcdeF...",
        "devices": ["dev1"]
    },
    "receive": {
        "address": "192.168.0.101",
        "devices": ["dev2"]
    }
}
```

A larger example is also included: `doc/config.json`

### Calling Python script directly

The Python scripts can be called directly without the wrapper script, but requires manually enabling or disabling the virtual environment:

Activate the virtual environment before the first run in a new commandline session:

    source venv/bin/activate

Use:

    ./thoscy-send.py -h

When finished, deactivate the virtual environment with:

    deactivate

Example Clients
---------------

![example use cases](media/example%20use%20cases.png)

A set of example clients are included:

* `pd/sendclient.pd`: Pure Data patch which sends OSC messages
* `pd/recvclient.pd`: Pure Data patch which receives OSC messages

Both examples should work together with the default address & ports on the same localhost:

    pd/sendclient.pd --OSC-> thoscy-send.py ----MQTT---> ThingsBoard server
    pd/recvclient.pd <-OSC-- thoscy-recv.py <-WebSocket- ThingsBoard server

First start thoscy-send or thoscy-recv, then start the affiliated client, ie. sendclient.pd & thoscy-send. To see data changing on the server, create/open a ThingsBoard Dashboard with widgets that show the device entity values.

### Multi

Additionally, a set of clients are included for working with multiple devices:

* `pd/multi-sendclient.pd`: Pure Data patch which sends OSC messages
* `pd/multi-recvclient.pd`: Pure Data patch which receives OSC messages

Like the clients above, they send to and receive from a ThingsBoard server, however these clients work with multiple devices and therefore require that:

1. thoscy-send is started with a gateway device token and one or more device name strings
2. thoscy-recv is started with one or more device ids

### Loopback

There is the `pd/loopback.pd` patch which pairs a sender and receiver with basic latency measurement.

Turn on random temperature messages and lower the message frequency in ms to see how quickly messages can be sent and received before matched send/recv pairs start to mix. Add maybe 20-50 ms on top of that for a basic effective update frequency. This value is likely based on network configuration, if sending over a local LAN or over the internet, ThingsBoard server resources, etc.

The Intelligent Museum
----------------------

An artistic-curatorial field of experimentation for deep learning and visitor participation

The [ZKM | Center for Art and Media](https://zkm.de/en) and the [Deutsches Museum Nuremberg](https://www.deutsches-museum.de/en/nuernberg/information/) cooperate with the goal of implementing an AI-supported exhibition. Together with researchers and international artists, new AI-based works of art will be realized during the next four years (2020-2023).  They will be embedded in the AI-supported exhibition in both houses. The Project „The Intelligent Museum” is funded by the Digital Culture Programme of the [Kulturstiftung des Bundes](https://www.kulturstiftung-des-bundes.de/en) (German Federal Cultural Foundation) and funded by the [Beauftragte der Bundesregierung für Kultur und Medien](https://www.bundesregierung.de/breg-de/bundesregierung/staatsministerin-fuer-kultur-und-medien) (Federal Government Commissioner for Culture and the Media).

As part of the project, digital curating will be critically examined using various approaches of digital art. Experimenting with new digital aesthetics and forms of expression enables new museum experiences and thus new ways of museum communication and visitor participation. The museum is transformed to a place of experience and critical exchange.

![Logo](media/Logo_ZKM_DMN_KSB.png)
