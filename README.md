# hp2mqtt

Python proxy script to communicate between [Rademacher](www.rademacher.de) HomePilot and MQTT broker. Mainly written to support [openhab](https://www.openhab.org/) integration but can be used for other implementations, too.
Be aware, the used Home Pilot interface is not officially supported by Rademacher. Therefore you use it on your own risk without warranty.
Inspirations for the project I took from [zigbee2mqtt](https://github.com/koenkk/zigbee2mqtt) and [io broker API implementation](https://github.com/homecineplexx/ioBroker.homepilot20).

# Requirements
You need the following by now:
 - python interpreter: *$ sudo apt-get  install  python2*, followed by *$ sudo apt-get  install python2*. There are some problems with latest Python 3 version, so better use version 2 until they are fixed.
 - Maybe additional python libraries like yaml must be installed in addition (script will blame missing libraries). Best by using pip installer like this: *$ pip install pyyaml*.
 - A running MQTT broker like [Mosquitto](https://mosquitto.org/).
 - A Rademacher HomePilot configured. You can test if the API is running by opening the following URL in a browser *http://[HomePilot IP address]/v4/devices* when connected to the same network as HomePilot. If successfull, you should see a JSON text output with several information about your devices like this:
 ![device api call](/readme_images/device_api_call.png)


# Installation
Clone the project or just copy the *hp2mqtt.py* and *hp2mqtt.yaml.sample* files to a directory.  Rename the sample file to *hp2mqtt.yaml* and open in editor. Enter a valid IP of your HomePilot to *hp_host*. Make a first run with the parameter *-d* for device identification: *$ python hp2mqtt.py -d*. You should get some logging on the screen and finally see a JSON construct with some device information.
![device log output](/readme_images/device_log.png)

Important is the *did*-part, this device number you need to assign the MQTT channel to your HomePilot device in the configuration file in the next step. You will find the device output in the *device-info.json* file in the data subdirectory, too.

Edit the *hp2mqtt.yaml* again and enter the requested data for mqtt connection in the upper section. In the device section create mapping entries along to your mqtt channel and the device id.
Test your configuration by running the script without parameter:

Install the libraries
```shell script
pip install paho.mqtt pyyaml requests
```
Run the application
```shell script
python hy2mqtt.py
```

# Usage
The script listens to your MQTT broker's configured *mqtt_channel* (default: *hp2mqtt*) and waits for messages.
As an example, a MQTT message */hp2mqtt/Rollershutter1/set 50* is received. The script tries to identify *Rollershutter1* device id along to the configuration file. If possible it tries to identify the following topic action *set*. Then it will check if the payload value is an integer between 0 and 100. If this is successfull it will send the API call to move Rollershutter1 at position 50% to the HomePilot.

If you send the same payload twice it indicates a stop. This is necessary because openhab does not explictly send a stop comand but 0 position. 

For more information about how to integrate mqtt binding in openhab please refer to [https://www.openhab.org/addons/bindings/mqtt/](https://www.openhab.org/addons/bindings/mqtt/). 
A possible configuration along to the sample-configuration is a MQTT Generic Thing with: 
 - state topic: hp2mqtt/Rollershutter1/state
 - command topic: hp2mqtt/Rollershutter1/set
 - incoming value transformation: JSONPATH:$.state

# Docker-Integration
For using inside an containered envirionment you can create a docker-image with Dockerfile. 
```shell script
docker build -t pduck27/hp2mqtt .
```
To pass you configuration you can use the the exported volume `/opt/hp2mqtt/data`. Use the volume `/opt/hp2mqtt/log` to export the log-files.
```shell script
docker run -d \ 
    -v {config-folder}:/opt/hp2mqtt/data \
    -v {log-folder}:/opt/hp2mqtt/log \ 
    pduck27/hp2mqtt 
```

- {config-folder} the full-qualified path to the data folder on the docker-host
- {log-folder} the full-qualified path to the log folder

# Limitations & issues
1. Hardware: Up to now I could only test it with Rollershutters like [Rollotron 1400 1440 and 1405](https://www.rademacher.de/smart-home/produkte/rollotron-standard-duofern-1400-1440-1405?productID=14234511) and Rollershutter actor [DuoFern Rohrmotor-Aktor 9471-1](https://www.rademacher.de/smart-home/produkte/rohrmotor-aktor-9471-1?productID=35140662) but as long as I see it will work with all other rollerhutters the same way. Not supported are intelligent switches, heating thermostat e.g.. 
But I think integration of them would be easy (io broker solution already has it:  [io broker API implementation](https://github.com/homecineplexx/ioBroker.homepilot20)). Additional conditions based on the unique  device number which identifies the product could make integration in the script simple. For example *device number* 14234511 are above mentioned rollershutters and 35000662 is the mentioned actor. 

2. State Topic: The state topic is not supported yet to request the state of rollershutters back when they are moved by using the manual switches.

So feel free to contribute to this project.

