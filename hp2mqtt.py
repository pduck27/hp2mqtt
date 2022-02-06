#import
from encodings import utf_8
import paho.mqtt.client as mqttClient
import time
import requests
import json
import sys
import yaml
import datetime
import atexit
import hashlib
import logging
import logging.handlers


#def 
def is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()


def normalize_deviceID(deviceid):
    # Normalizing device_id, because sometimes they have an additional _<Character> at the end
    deviceid_str = str(deviceid)
    if deviceid_str.find("_") != -1:
        deviceid_str = deviceid_str[0:deviceid_str.index("_")]

    return deviceid_str


def log_message(message, level):
    logger.log(level, message)
    
    now = datetime.datetime.now()
    message = now.strftime("%d.%m.%Y %H:%M:%S  ") + message
    print (str(message))


def close_logfile():
    logging.shutdown  


def try_HomePilotAuthentication():    
    response = None
    try:      
        return_data = {}
        response = requests.post(hp_host + "/authentication/password_salt")        
        if response.status_code == 200:
            # get password_salt
            return_data = response.json()            
            pwd = hashlib.sha256()
            pwd.update(hp_pwd.encode())
            
            # build pass-string with salt and individual password
            pwd_salted = hashlib.sha256()
            pwd_salted.update(return_data["password_salt"].encode())
            pwd_salted.update(pwd.hexdigest().encode())

            send_data = json.loads(hp_send_data_login_tmpl)     
            send_data["password"] = pwd_salted.hexdigest()
            send_data["password_salt"] = return_data["password_salt"]            
            
            response = requests.post(hp_host + "/authentication/login", json=send_data, headers=headers)
            if response.status_code == 200:                
                global cookies
                cookies = response.cookies
                log_message("Authentication was successfully, got a tasty cookie :) ", logging.INFO)
            else:
                raise Exception("%s: %s" % (response.status_code, response.text))

        else:
            raise Exception("Error while getting password salt: %s: %s" % (response.status_code, response.text))

        
    except Exception as e :        
        if response is None :
            log_message("Authentication error: %s" % (str(e)), logging.ERROR)
        else:
            if response.status_code == 500:
                json_data = json.loads(response.text)
                if json_data["error_code"] == 5007:
                    log_message("Authentication is disabled, continue without password.", logging.INFO)
                    return

            log_message("Authentication error, maybe wrong password? %s" % (response.text), logging.ERROR)

        raise SystemExit(e)


def try_requestActorDeviceUpdate():
    log_message("Update actor device states %s" % (hp_host), logging.INFO)
    mqtt_items_state = {}
    try:
        # Read actor devices and send status
        response = requests.get("%s/%s" % (hp_host, hp_devices_url_list_part), cookies=cookies)
        log_message("Connection for actor devices established successfully.", logging.DEBUG)            
        parsed_json = (json.loads(response.text))
        for mqtt_item in mqtt_items:
            for hp_device in parsed_json["devices"]:
                if hp_device["did"] == mqtt_items[mqtt_item][0]:
                    #log_message(str(hp_device["statusesMap"]), logging.DEBUG)
                    mqtt_items_state[mqtt_item] = hp_device["statusesMap"]
                    if mqtt_items[mqtt_item][2].lower() == "heating":
                        mqtt_items_state[mqtt_item]["Position"] = mqtt_items_state[mqtt_item]["Position"] / 10
                        mqtt_items_state[mqtt_item]["acttemperatur"] = mqtt_items_state[mqtt_item]["acttemperatur"] / 10
               
        if (not mqtt_items_state is None):           
            log_message("Actor status found: %s" % (mqtt_items_state), logging.DEBUG)                                                             
            for mqtt_item_state in mqtt_items_state:                     
                client.publish("%s/%s/status" % (mqtt_channel, mqtt_item_state), json.dumps(mqtt_items_state[mqtt_item_state]))                     
            
    except Exception as e:
        log_message("Error during MQTT actor status update: %s" % (str(e)), logging.ERROR)
        raise SystemExit(e)


def try_requestMeterDeviceUpdate():
    log_message("Update meter states %s" % (hp_host), logging.INFO)
    mqtt_items_state = {}
    try:        
        # Read meter devices and send status
        response = requests.get("%s/%s" % (hp_host, hp_meter_url_list_part), cookies=cookies)
        log_message("Connection for meters established successfully.", logging.DEBUG)            
        parsed_json = (json.loads(response.text))
        for mqtt_item in mqtt_items:
            for hp_device in parsed_json["meters"]:
                if hp_device["did"] == mqtt_items[mqtt_item][0]:
                    #log_message(str(hp_device["statusesMap"]), logging.DEBUG)
                    mqtt_items_state[mqtt_item] = hp_device["readings"]  
        
        if (not mqtt_items_state is None):           
            log_message("Meter status found: %s" % (mqtt_items_state), logging.DEBUG)                                                             
            for mqtt_item_state in mqtt_items_state:                     
                client.publish("%s/%s/status" % (mqtt_channel, mqtt_item_state), json.dumps(mqtt_items_state[mqtt_item_state]))                     
            
    except Exception as e:
        log_message("Error during MQTT meter status update: %s" % (str(e)), logging.ERROR)
        raise SystemExit(e)


def try_deviceInitialization():
    # get device list and add device number for later type identification to own items
    # also write config file if requested
    global mqtt_items 
    mqtt_items_new = {}
    log_message("Request HomePilot active device list: %s" % (hp_host), logging.INFO)
    try:
        
        # 1. Initially reading of actors
        response = requests.get("%s/%s" % (hp_host, hp_devices_url_list_part), cookies=cookies)        
        log_message("Connection for reading actors established successfully.", logging.INFO)                
        parsed_json = (json.loads(response.text))        

        # Debugging start: can be overload by reading configuration from file an not from HomePilot for debugging purpose
        # with open("data/device_info.json", "r") as read_file:
        #   parsed_json = json.load(read_file)            
        #   log_message("json file load success")                           
        # Debugging end
        
        for hp_device in parsed_json["devices"]:
            log_message("Search device number for device with did = %s" % (hp_device["did"]), logging.DEBUG)
            if hp_device["did"] in mqtt_items.values():
                for mqtt_item in mqtt_items:                
                    if mqtt_items[mqtt_item] == hp_device["did"]:
                        property_list = list()
                        property_list.append(hp_device["did"])
                        property_list.append(int(normalize_deviceID(hp_device["deviceNumber"])))                    
                        if device_mapping.get(int(normalize_deviceID(hp_device["deviceNumber"]))):
                            property_list.append(device_mapping[int(normalize_deviceID(hp_device["deviceNumber"]))])
                        else:
                            raise Exception("Device with did %s couldn't configure because of missing number mapping for device type %s in file '%s'" % (property_list[0], property_list[1], mapping_file_name), logging.ERROR)
                        mqtt_items_new[mqtt_item] = property_list
                        log_message("Device with did %s found. Added with device number %s and mapped type '%s'." % (property_list[0], property_list[1], property_list[2]), logging.INFO)
                        break
            else:                
                log_message("Device with did %s is not configured and will be ignored." % (hp_device["did"]), logging.WARNING)
      
        # If requested via startup parameter -F write configuration for actors
        for argument in sys.argv: 
            match argument.upper():
                case "-F":
                    log_message(json.dumps(parsed_json, indent=4, sort_keys=True), logging.INFO)            
                    device_info_file = open(device_file_name, "w")            
                    device_info_file.write(str(response.text.encode().strip()))
                    device_info_file.close            
                    log_message("File %s updated with current device info." % (device_file_name), logging.INFO)                
               
        # 2. Initially reading of meters
        response = requests.get("%s/%s" % (hp_host, hp_meter_url_list_part), cookies=cookies)        
        log_message("Connection for reading meters established successfully.", logging.INFO)                
        parsed_json = (json.loads(response.text))        

        # Debugging start: can be overload by reading configuration from file an not from HomePilot for debugging purpose
        # with open("data/meter_info.json", "r") as read_file:
        #   parsed_json = json.load(read_file)            
        #   log_message("json file load success", logging.DEBUG)                           
        # Debugging end
        
        for hp_device in parsed_json["meters"]:
            log_message("Search device number for meter with did = %s" % (hp_device["did"]), logging.DEBUG)
            if hp_device["did"] in mqtt_items.values():
                for mqtt_item in mqtt_items:                
                    if mqtt_items[mqtt_item] == hp_device["did"]:
                        property_list = list()
                        property_list.append(hp_device["did"])
                        property_list.append(int(normalize_deviceID(hp_device["deviceNumber"])))                    
                        if device_mapping.get(int(normalize_deviceID(hp_device["deviceNumber"]))):
                            property_list.append(device_mapping[int(normalize_deviceID(hp_device["deviceNumber"]))])
                        else:
                            raise Exception("Meter with did %s couldn't configure because of missing number mapping for device type %s in file '%s'" % (property_list[0], property_list[1], mapping_file_name), logging.ERROR)
                        mqtt_items_new[mqtt_item] = property_list
                        log_message("Meter with did %s found. Added with device number %s and mapped type '%s'." % (property_list[0], property_list[1], property_list[2]), logging.INFO)
                        break
            else:                
                log_message("Meter with did %s is not configured and will be ignored." % (hp_device["did"]), logging.WARNING)
      
        # If requested via startup parameter -F write configuration 
        for argument in sys.argv: 
            match argument.upper():
                case "-F":
                    log_message(json.dumps(parsed_json, indent=4, sort_keys=True), logging.INFO)            
                    device_info_file = open(meter_file_name, "w")            
                    device_info_file.write(str(response.text.encode().strip()))
                    device_info_file.close            
                    log_message("File %s updated with current meter info." % (meter_file_name), logging.INFO)
                    log_message("Exit application now.", logging.INFO)
                    sys.exit(0)

        # Finalization
        mqtt_items = mqtt_items_new
        log_message("Final configuration in use: %s" % (str(mqtt_items)), logging.INFO)

    except requests.exceptions.RequestException as e:
        log_message("Could not connect to HomePilot at %s. Please check if IP and Login is valid. %s" % (hp_host, str(e)), logging.ERROR)
        raise SystemExit(e)

    except Exception as e:
        log_message("Error during device configuration reading: %s" % (str(e)), logging.ERROR)
        raise SystemExit(e)


def on_connectMQTTBroker(client, userdata, flags, rc):
    if rc == 0:
        log_message("Connected to mqtt broker.", logging.INFO)
        global mqtt_connected                
        mqtt_connected = True                
    else:
        log_message("Connection to mqtt broker failed.", logging.ERROR)


def on_receiveMQTTMessage(client, userdata, message):      
    log_message("Received message: %s %s" % (message.topic, message.payload.decode()), logging.INFO)

    #validate message with channel, topic, action and item id    
    topic_arr = message.topic.split("/")
    try:
        if topic_arr[0] != mqtt_channel :
            raise Exception("MQTT Channel mismatchs. Expected: %s" % (mqtt_channel))
        elif topic_arr[1] == "" :
            raise Exception("MQTT topic not identified.")
        elif topic_arr[2] == "" : 
            raise Exception("MQTT message not identified.")
        
        curr_device_name = topic_arr[1].lower()
        curr_topic_cmd = topic_arr[2].lower()
        curr_topic_payload = message.payload.lower().decode()
        if curr_topic_cmd == "status":
            log_message("Ignore processing of state message.", logging.DEBUG)
            return
        else:
            log_message("Identified valid incoming mqtt message: %s/%s/%s %s" % (topic_arr[0], curr_device_name, curr_topic_cmd, curr_topic_payload), logging.DEBUG)
        
        if mqtt_items.get(curr_device_name):                        
            curr_device_did = mqtt_items[curr_device_name][0]            
            curr_device_number = mqtt_items[curr_device_name][1]             
            curr_device_type = mqtt_items[curr_device_name][2].lower()            
        else:
            raise Exception("Device '%s' not found, please check your configuration." % (topic_arr[1]), logging.ERROR)

        log_message("Identified target device with did %s and device number %s of type '%s'" % (curr_device_did, curr_device_number, curr_device_type), logging.DEBUG)

    except Exception as e :        
        log_message("Error while investigating incoming mqtt message: %s" % (str(e)), logging.ERROR)
        return

    #execute comand
    if curr_topic_cmd == "set" :
        
        # check if stop comand should be send (same payload than last comand for this device)
        try:
            if is_integer(curr_topic_payload) and curr_device_type == "rollershutter":
                new_last_cmd_value = curr_topic_payload
                if curr_device_did in mqtt_last_cmd:
                    log_message("Last comand for %s was '%s'." % (curr_device_name, mqtt_last_cmd[curr_device_did]), logging.DEBUG)
                    if mqtt_last_cmd[curr_device_did] == curr_topic_payload:
                        log_message("Last comand '%s' is same as new comand, so I will send STOP comand." % (curr_topic_payload), logging.DEBUG)
                        curr_topic_payload = "stop"
                        new_last_cmd_value = ""                    
                else:
                    log_message("No last comand found for %s" % (curr_device_name), logging.DEBUG)

                mqtt_last_cmd[curr_device_did] = new_last_cmd_value
                log_message("Remember last comand '%s' for %s" % (new_last_cmd_value, curr_device_name), logging.DEBUG)         

        except Exception as e :
            log_message("Stop comand check was unsuccessful: %s" % (str(e)), logging.ERROR)
            return

        # prepare comand
        try:
            global mqtt_actor_countdown
            new_actor_update_countdown = mqtt_actor_countdown
            send_comand = "%s/%s/%s" % (hp_host, hp_devices_url_cmd_part, curr_device_did)  
            send_data = ""  

            # rollershutter
            if curr_device_type == "rollershutter":          
                if is_integer(curr_topic_payload):
                    if int(curr_topic_payload) >= 0 and int(curr_topic_payload) <= 100 :    
                        send_data = json.loads(hp_send_data_gotopos_tmpl)     
                        send_data["value"] = curr_topic_payload    
                        new_actor_update_countdown = 15    
                    else:
                        raise Exception("Can not process payload: %s" % (curr_topic_payload))

                
                elif str(curr_topic_payload) == "stop":                
                    send_data = json.loads(hp_send_data_stop_tmpl)  
                    new_actor_update_countdown = 3
                else:
                    raise Exception("Can not process payload: %s" % (curr_topic_payload))
            
            # switch
            elif curr_device_type == "switch": 
                if str(curr_topic_payload) in ["on", "1", "100"]:                
                    send_data = json.loads(hp_send_data_on_tmpl) 

                #is OFF comand  like for a switch
                elif str(curr_topic_payload) in ["off", "0"]:                
                    send_data = json.loads(hp_send_data_off_tmpl) 

                else:
                    raise Exception("Can not process payload: %s" % (curr_topic_payload))

                new_actor_update_countdown = 5

            # heating (no further check for integer values because of different formats)
            elif curr_device_type == "heating":                 
                send_data = json.loads(hp_send_data_temperature_tmpl)     
                send_data["value"] = curr_topic_payload  
                new_actor_update_countdown = 5
               

            # not implemented 
            else:
                raise Exception("Comand '%s' for device type '%s' is not implemented." % (curr_topic_payload, curr_device_type))

        except Exception as e :
            log_message("Error during comand creation: %s" % str(e), logging.ERROR)
            return

        # send comand        
        try:   
            log_message("Try to send : %s with %s." % (send_comand, json.dumps(str(send_data))), logging.INFO)            
            response = requests.put(send_comand, json.dumps(send_data), headers=headers, cookies=cookies)             
            parsed_json = json.loads(response.text)            
            log_message("Result: %s" % (parsed_json["error_description"]), logging.INFO)
            mqtt_actor_countdown = new_actor_update_countdown

        except Exception as e :
            log_message("Request to HomePilot was unsuccessful: %s" % (str(e)), logging.ERROR)
            return

def on_publishMQTTMessage(client,userdata,result):             #create function for callback
    log_message("State published successfully: %s " % (result), logging.DEBUG)

# main
#variables
headers = {"Content-Type": "application/json"}
cookies = {}
cfg_file_name = "data/hp2mqtt.yaml"
mapping_file_name = "data/devicemapping.yaml"
device_mapping = {}
log_file_name = "log/hp2mqtt.log"        
log_bck_file_name = "log/hp2mqtt"    
device_file_name = "data/device_info.json"
meter_file_name = "data/meter_info.json"
client = mqttClient.Client()  

mqtt_connected = False
mqtt_broker_address= "localhost"
mqtt_port = 1883
mqtt_user = ""
mqtt_password = ""
mqtt_channel = "hp2mqtt"
mqtt_items = {}
mqtt_last_cmd = {}
mqtt_actor_update_sec = 300
mqtt_actor_countdown = 300
mqtt_meter_update_sec = 300
mqtt_meter_countdown = 300

hp_host = "http://"
hp_pwd = ""
hp_devices_url_cmd_part = "devices"
hp_devices_url_list_part = "v4/devices"
hp_meter_url_list_part = "v4/devices?devtype=Sensor"
hp_send_data_gotopos_tmpl = '{"name": "GOTO_POS_CMD", "value": "0"}'
hp_send_data_stop_tmpl = '{"name": "STOP_CMD"}'
hp_send_data_on_tmpl = '{"name": "TURN_ON_CMD"}'
hp_send_data_off_tmpl = '{"name": "TURN_OFF_CMD"}'
hp_send_data_temperature_tmpl = '{"name": "TARGET_TEMPERATURE_CFG", "value": "0"}'
hp_send_data_login_tmpl = '{"password": "saltedPassword", "password_salt": "passwordSalt"}'

# if requested via startup parameter -D log on debug level
new_log_level = logging.INFO
if ("-D" in sys.argv) or ("-d" in sys.argv):
    new_log_level = logging.DEBUG

logging.basicConfig(filename=log_file_name, filemode='w', encoding='utf-8', format='%(asctime)s - %(levelname)s - %(message)s', level=new_log_level)  
logger = logging.getLogger('my_logger')
handler = logging.handlers.RotatingFileHandler(log_file_name, maxBytes=5000000, backupCount=10, delay=True) #TODO 5000000
logger.addHandler(handler)

#for _ in range(10000): # TODO test logging
#    log_message("Hello, world!", logging.INFO) # TODO test logging

log_message("Log level set to: %s." %(logging._levelToName[new_log_level]), logging.INFO)


# register logging shutdown on termination
atexit.register(close_logfile)  

# read configuration files
try:
    
    # custom configuration file
    with open(cfg_file_name) as file:
        config_dict = yaml.safe_load(file)

        # system settings
        config_dict_sys = config_dict["system"]

        if config_dict_sys.get("mqtt_user"):          
            mqtt_user = config_dict_sys["mqtt_user"]
        
        if config_dict_sys.get("mqtt_password"): 
            mqtt_password = config_dict_sys["mqtt_password"]

        if config_dict_sys.get("mqtt_broker_address"): 
            mqtt_broker_address = config_dict_sys["mqtt_broker_address"]

        if config_dict_sys.get("mqtt_port"): 
            mqtt_port = config_dict_sys["mqtt_port"]

        if config_dict_sys.get("mqtt_channel"): 
            mqtt_channel = config_dict_sys["mqtt_channel"]       

        if config_dict_sys.get("hp_pwd"):
            hp_pwd = config_dict_sys["hp_pwd"]
        
        if config_dict_sys.get("hp_host"): 
            hp_host = hp_host + config_dict_sys["hp_host"]

        if config_dict_sys.get("mqtt_actor_update_sec"):
            mqtt_actor_update_sec = config_dict_sys["mqtt_actor_update_sec"]

        if config_dict_sys.get("mqtt_meter_update_sec"):
            mqtt_meter_update_sec = config_dict_sys["mqtt_meter_update_sec"]

        # devices        
        for device in config_dict["devices"]:
            mqtt_items[device.lower()] = config_dict["devices"][device]
            #log_message("Imported item '%s' with did %s from configuration file." % (str(device), config_dict["devices"][device]))
                 
        log_message("Configuration successfully loaded: %s." % (str(mqtt_items)), logging.INFO)

    # device mapping file
    with open(mapping_file_name) as file:
        device_mapping = yaml.safe_load(file)                
        device_mapping = device_mapping["mapping"]

        log_message("Device mapping successfully loaded for the following device types: %s" % (str(device_mapping)), logging.INFO)


except Exception as e:
    log_message("Error while reading configuration file: %s" % (str(e)), logging.ERROR)
    raise SystemExit(e)

# try authorization request
try_HomePilotAuthentication()

# try device initial update
try_deviceInitialization()

# initiate mqtt connection
client.username_pw_set(mqtt_user, mqtt_password)    
client.on_connect= on_connectMQTTBroker                      
client.on_message= on_receiveMQTTMessage   
client.on_publish = on_publishMQTTMessage                        

client.connect(mqtt_broker_address, mqtt_port)  
client.loop_start() 

while mqtt_connected != True:    
    time.sleep(0.1)

client.subscribe(mqtt_channel + "/#" )
log_message("Listen to: %s /#" % (mqtt_channel), logging.INFO)

# try first state updates
try_requestActorDeviceUpdate()
try_requestMeterDeviceUpdate()

# main loop
mqtt_actor_countdown = mqtt_actor_update_sec
mqtt_meter_countdown = mqtt_meter_update_sec
try:
    while True:
        time.sleep(1)        
        
        # read actors
        mqtt_actor_countdown -= 1        
        if mqtt_actor_countdown == 0:
            try:
                mqtt_actor_countdown -= 1        
                try_requestActorDeviceUpdate()
            finally:
                mqtt_actor_countdown = mqtt_actor_update_sec  

        # read meters
        mqtt_meter_countdown -= 1
        if mqtt_meter_countdown == 0:
            try:
                mqtt_meter_countdown -= 1
                try_requestMeterDeviceUpdate()
            finally:
                mqtt_meter_countdown = mqtt_meter_update_sec  

        log_message("Next actor update in: %s" % (mqtt_actor_countdown), logging.DEBUG)
        log_message("Next meter update in: %s" % (mqtt_meter_countdown), logging.DEBUG)


except KeyboardInterrupt:
    log_message("Exiting", logging.INFO)
    client.disconnect()
    client.loop_stop()
