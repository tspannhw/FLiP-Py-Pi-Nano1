from time import sleep
from math import isnan
import time
import argparse
import sys
import datetime
import subprocess
import sys
import os
import datetime
import traceback
import math
import base64
import json
from time import gmtime, strftime
import random, string
import psutil
import base64
import uuid
import socket 
from mics6814 import MICS6814
from sgp30 import SGP30
import bme680
import pulsar
import logging
from pulsar.schema import *
from pulsar.schema import AvroSchema
from pulsar.schema import JsonSchema
from pulsar import Client, AuthenticationOauth2

### Schema Object
# https://pulsar.apache.org/docs/en/client-libraries-python/
# https://pulsar.apache.org/api/python/

class NanoOne(Record):
    cpu = Float()
    diskusage = String()
    endtime = String()
    equivalentco2ppm = String()
    host = String()
    hostname = String()
    ipaddress = String()
    macaddress = String()
    memory = Float()
    rowid = String()
    runtime = Integer()
    starttime = String()
    systemtime = String()
    totalvocppb = String()
    bme680_tempc = Float()
    bme680_tempf = Float()
    bme680_pressure = Float()
    bme680_humidity = Float()
    gasoxidising = Float()
    gasadc = Float()
    gasreducing = Float()
    gasnh3 = Float()
    ts = Integer()
    uuid = String()

# parse arguments
parse = argparse.ArgumentParser(prog='nano1.py')
parse.add_argument('-su', '--service-url', dest='service_url', type=str, required=True,
                   help='The pulsar service you want to connect to')
parse.add_argument('-t', '--topic', dest='topic', type=str, required=True,
                   help='The topic you want to produce to')
parse.add_argument('-n', '--number', dest='number', type=int, default=1,
                   help='The number of message you want to produce')
parse.add_argument('--auth-params', dest='auth_params', type=str, default="",
                   help='The auth params which you need to configure the client')
args = parse.parse_args()


# Smooths wobbly data. Increase to increase smoothing.
mean_size = 20

# Compares current smoothed value to smoothed value x
# readings ago. Decrease this to increase detection
# speed.
delta_size = 10

# The delta threshold at which a change is detected.
# Decrease to make the detection more sensitive to
# fluctuations, increase to make detection less
# sensitive to fluctuations.
threshold = 10

data = []
means = []

sgp30 = SGP30()
sgp30.start_measurement()

external_IP_and_port = ('198.41.0.4', 53)  # a.root-servers.net
socket_family = socket.AF_INET

def IP_address():
        try:
            s = socket.socket(socket_family, socket.SOCK_DGRAM)
            s.connect(external_IP_and_port)
            answer = s.getsockname()
            s.close()
            return answer[0] if answer else None
        except socket.error:
            return None

# Get MAC address of a local interfaces
def psutil_iface(iface):
    # type: (str) -> Optional[str]
    import psutil
    nics = psutil.net_if_addrs()
    if iface in nics:
        nic = nics[iface]
        for i in nic:
            if i.family == psutil.AF_LINK:
                return i.address
# Random Word
def randomword(length):
 return ''.join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ".lower()) for i in range(length))

# Fixed
packet_size=3000
host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)
ipaddress = IP_address()

print(args.service_url)
print(args.auth_params)

if (len(args.auth_params) == 0 ):
   client = pulsar.Client(args.service_url)
else:
   client = pulsar.Client(args.service_url, authentication=AuthenticationOauth2(args.auth_params))

producer = client.create_producer(topic=args.topic ,schema=JsonSchema(NanoOne),properties={"producer-name": "nano1-py-sensor","producer-id": "nano1-sensor" })

gas = MICS6814()
gas.set_led(0,0,0)   # turn off light


try:
    while True:
        currenttime = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        starttime = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        start = time.time()
        uniqueid = 'nano1uuid{0}{1}'.format(randomword(3),strftime("%Y%m%d%H%M%S",gmtime()))
        uuid2 = '{0}_{1}'.format(strftime("%Y%m%d%H%M%S",gmtime()),uuid.uuid4())
        result = sgp30.get_air_quality()
        usage = psutil.disk_usage("/")
        # bme680
        try:
            sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
        except IOError:
            sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

        sensor.set_humidity_oversample(bme680.OS_2X)
        sensor.set_pressure_oversample(bme680.OS_4X)
        sensor.set_temperature_oversample(bme680.OS_8X)
        sensor.set_filter(bme680.FILTER_SIZE_3)
        sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
        sensor.set_gas_heater_temperature(320)
        sensor.set_gas_heater_duration(150)
        sensor.select_gas_heater_profile(0)

        gardenRec = NanoOne()

        end = time.time()

        gardenRec.cpu = psutil.cpu_percent(interval=1)
        gardenRec.diskusage = "{:.1f} MB".format(float(usage.free) / 1024 / 1024)
        gardenRec.endtime  = '{0}'.format(str(end))
        gardenRec.equivalentco2ppm = '{:5d}'.format( (result.equivalent_co2))
        gardenRec.host  = os.uname()[1]
        gardenRec.hostname  = host_name
        gardenRec.ipaddress = ipaddress
        gardenRec.macaddress  = psutil_iface('wlan0')
        gardenRec.memory = psutil.virtual_memory().percent
        gardenRec.rowid =  str(uuid2)
        gardenRec.runtime  = int(round(end - start)) 
        gardenRec.systemtime = str(datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S'))
        gardenRec.totalvocppb = '{0:3d}'.format(result.total_voc)
        gardenRec.bme680_tempc = float('{0:.2f}'.format(sensor.data.temperature))
        gardenRec.bme680_tempf = float('{0:.2f}'.format((sensor.data.temperature * 1.8) + 32))
        gardenRec.bme680_pressure = float('{0:.2f}'.format(sensor.data.pressure))
        gardenRec.bme680_humidity = float('{0:.3f}'.format(sensor.data.humidity))
        gardenRec.gasoxidising =  round(gas.read_all().oxidising,2)
        gardenRec.gasadc = round(gas.read_all().adc,2)
        gardenRec.gasreducing = round(gas.read_all().reducing,2)
        gardenRec.gasnh3 = round(gas.read_all().nh3,2)
        gardenRec.ts =  int(time.time())
        gardenRec.uuid = str(uniqueid)
        gardenRec.runtime =  int(round(end - start)) 
        gardenRec.starttime = str(starttime)

        print(gardenRec)

        # producer.send(gardenRec,partition_key=str(uniqueid))
except KeyboardInterrupt:
    pass

client.close()
