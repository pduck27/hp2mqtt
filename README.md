# hp2mqtt

hp2mqtt is a python proxy script to interact between [Rademacher](www.rademacher.de) HomePilot and a MQTT broker. It was mainly written to support [openhab](https://www.openhab.org/) communication to Rademacher HomePilot but it can be used for other implementations, too.
Be aware, the used Home Pilot interface is not officially supported by Rademacher. Therefore you use it on your own risk without warranty.

Inspirations for the project I took from [zigbee2mqtt](https://github.com/koenkk/zigbee2mqtt) and [io broker API implementation](https://github.com/homecineplexx/ioBroker.homepilot20). I also got a well support from Rademacher to realize it.

# Requirements
You need the following by now:
 - Python 3.10 or later interpreter: *$ sudo apt-get  install python3.10*, followed by *$ sudo apt-get  install python3*.
 - Maybe additional python libraries like paho-mqtt, requests and yaml must be installed in addition (script will blame missing libraries). Best by using pip installer like this: 
```shell script
pip install paho.mqtt pyyaml requests
```
 - A running MQTT broker like [Mosquitto](https://mosquitto.org/).
 - A Rademacher HomePilot configured. You can test if the API is running by opening the following URL in a browser *http://[HomePilot IP address]/v4/devices* when connected to the same network as HomePilot. If successfull, you should see a JSON text output with several information about your devices like this:
 ![device api call](/readme_images/device_api_call.png)


# Installation
Clone the project or just copy the *hp2mqtt.py* file and the */data* directory to a local directory.  Rename the sample configuration file *hp2mqtt.yaml.sample* in */data* directory to *hp2mqtt.yaml* and open it in an editor. Enter a valid IP of your HomePilot for *hp_host* and, if used, your password for *hp_pwd*. Make a first script run with the parameter *-F* for device identification: 
```
python hp2mqtt.py -F
```
You should get some logging on the screen and finally see a JSON construct with some device information like this. It is also exported as *device_info.json* and *meter_info.json* file in your */data* directory.

![device log output](/readme_images/device_log.png)

If not, you will get some error messages, maybe a password is missing or the host address is wrong. 
Regarding the device information from HomePilot the most important part is the *did*-part. This unique *device id* is needed to assign the MQTT channel to your HomePilot device in the configuration file in the next step. 
Please be aware, some devices have an "_A" or "_S" suffix at the end of the *did*. Please ignore them, just use the number part before the underscore. The script will cut the suffix away if necessary.

Edit the *hp2mqtt.yaml* again and enter the requested data for MQTT connection in the upper section. There you can also set the cycle in seconds for actor (mqtt_actor_update_sec) and meter (mqtt_meter_update_sec) state update to the MQTT broker. In the device section create mapping entries along to your mqtt channel and the device id. 

Test your configuration by running the script without parameter:
```shell script
python hp2mqtt.py
```

If necessary, you could add the following parameters:
```
python hp2mqtt.py <-F> <-D>

-F --> Exports the configuration json files for actors and meters from HomePilot to your /data directory.

-D --> Logs more detailled debug messages to solve issues.
```

Another important file is the *devicemapping.yaml* in the */data* directory. Next to the *did*, which is the unique device id in your HomePilot, you also find a *DeviceNumber* in the devices list. This is a kind of unique model id from Rademacher. For example the *14234511* corresponds to *RolloTron Standard DuoFern 1400/1440/1405* devices. 

The devicemapping file in the project contains in the first section all devices I know or copied from io-broker implementation. This is just for your information of supported devices. 

In the second part *mapping* you tell the script how to tread your own devices (e.g. like a rollershutter, switch). So if your device number is not there you can just add the number and the type in the mapping section. The ones you find in the sample file in section *mapping* are those I could test. 

Please let me know when you could test additional types or update the project. Sounds complicate? Maybe but with this solution you do not need to change the script when a new device is on the market and you get an idea which device types are supported (in the *mapping* section of the project here), which one should work (listed under *knowndevices* but not in *mapping* section) and which ones are unknown. 

FYI: The environment meter will appear twice. Once as an actor and second as meter with two different did's. You must add both to your *hp2mqtt.yaml*. In the *devicemapping.yaml*  file it is mapped as a rollershutter for the actor.


# Usage
The script listens to your MQTT broker's configured *mqtt_channel* (default: *hp2mqtt*) and waits for messages.

As an example, a MQTT message */hp2mqtt/Rollershutter1/set 50* is received. The script tries first to identify *Rollershutter1* device id along to the configuration file and checks the device type mapping (e.g. rollershutter). If this was successfull it tries to identify the following topic action *set* and the given payload after *set*. 
For rollershutter types  it will check if the payload value is an integer between 0 and 100. If this is successfull it will send the API call to move *Rollershutter1* at position 50% to the HomePilot. If you send the same payload twice it indicates a stop. This is necessary because openhab does not explictly send a stop comand but 0 position. 

For switch types the set comand accepts *on*, *1*, *100* or *off*, *0* values.

For heating type the set comand accepts everything because of different number formats and units of measure. But it should be a kind of valid integer or decimal number finally. If not, you will get an error from the HomePilot.

For more information about how to integrate mqtt binding in openhab please refer to [https://www.openhab.org/addons/bindings/mqtt/](https://www.openhab.org/addons/bindings/mqtt/). 
A possible configuration along to the sample-configuration is a MQTT Generic Thing with: 
 - state topic: hp2mqtt/Rollershutter1/status
 - command topic: hp2mqtt/Rollershutter1/set
 - incoming value transformation: JSONPATH:$.status

 The script supports a periodical status request. Each *mqtt_actor_update_sec* seconds it checks all actors and sends a payload of the *statusesMap*-part of Home Pilot's response (you remember the one you checked the did value with?) to the mqtt channel status. The same it does all *mqtt_meter_update_sec* for the meters.

 For a rollershutter it looks like this: {"Manuellbetrieb": 0, "Position": 95} where *Position* is the shutter position in percent. You can get it via JSONPATH like this *JSONPATH:$.Position*.

 For a heating controls it looks like this: {"Manuellbetrieb": 0, "Position": 180, "acttemperatur": 216} where *Position* is the target temperatur and *acttemperatur* is the current one. Actually I divide the value by 10 before sending it as payload. 

 The environment meter sends this: {"sun_detected":false,"sun_brightness":26000,"sun_direction":162.0,"sun_elevation":54,"wind_speed":0.0,"rain_detected":false,"temperature_primary":14.8}. Temperature does not need to be prepared like for heating.
 

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
Up to now I could test it with the following hardware components:
 - Rollershutters like [Rollotron 14* and 18* series](https://www.rademacher.de/smart-home/produkte/rollotron-standard-duofern-1400-1440-1405?productID=14234511)
 - Rollershutter actor [DuoFern Rohrmotor-Aktor 9471-1](https://www.rademacher.de/smart-home/produkte/rohrmotor-aktor-9471-1?productID=35140662)
 - Rollershutter control [Troll Comfort 5665](https://www.rademacher.de/shop/rollladen-sonnenschutz/steuerung/troll-comfort-duofern-5665-uw)
 - Switch [DuoFern Zwischenstecker Schalten 9472](https://www.rademacher.de/smart-home/produkte/duofern-zwischenstecker-schalten-9472?productID=35001164)
 - Heating Control [DuoFern Heizkörperstellantrieb 9433 (Version 1)](https://www.rademacher.de/smart-home/produkte/duofern-heizkoerperstellantrieb-9433?productID=35003074)
 - Environment Meter [DuoFern Umweltsensor](https://www.rademacher.de/shop/rollladen-sonnenschutz/sensoren/duofern-umweltsensor-9475)
 
 But as long as I see it will work with all other devices of the same family in the same way. Please check the mappingfile for *knowndevices* which should work.
 
 # Latest release notes
 - Update to run on Python 3.10 or later
 - Supports two cycles for actor and meter state with different delays
 - Integrated Python logging with log rotation
 - Added additional debug parameter for extended logging
 
