#import
import paho.mqtt.client as mqttClient
import time
import requests
import json
import sys
import yaml
import datetime
import atexit

#def 
def is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()

def close_logfile():
    global log_file
    log_file.close

def log_message(message):
    now = datetime.datetime.now()
    message = now.strftime("%d.%m.%Y %H:%M:%S  ") + message
    print (str(message))
    global log_file
    log_file.write(message + "\n")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log_message("Connected to mqtt broker")
        global mqtt_connected                
        mqtt_connected = True                
    else:
        log_message("Connection to mqtt broker failed")

def on_set_message(client, userdata, message):      
    log_message("Received message: %s %s" % (message.topic, message.payload))

    #validate message with channel, topic, action and item id    
    topic_arr = message.topic.split("/")
    try:
        if topic_arr[0] != mqtt_channel :
            raise Exception("MQTT Channel mismatchs. Expected -> " + mqtt_channel)
        elif topic_arr[1] == "" :
            raise Exception("MQTT item not identified")
        elif topic_arr[2] == "" : 
            raise Exception("MQTT message not identified")
        else:
            log_message("Identified valid mqtt message: %s/%s/%s %s" % (topic_arr[0], topic_arr[1], topic_arr[2], message.payload))

        curr_item = mqtt_items.get(topic_arr[1]) 
        log_message("Identified valid item id: " + curr_item)

    except Exception as e :        
        log_message("Invalid mqtt message: " + str(e))
        return

    #execute comand
    if topic_arr[2] == "set" :
        # check if stop comand (sends same payload than last comand)
        try:
            new_last_cmd_value = message.payload
            if curr_item in mqtt_last_cmd:
                log_message("Last cmd found for %s: %s" % (curr_item, mqtt_last_cmd[curr_item]))
                if mqtt_last_cmd[curr_item] == message.payload:
                    log_message("Last cmd is new comand, so I will send STOP cmd.")
                    message.payload = "STOP"
                    new_last_cmd_value = ""                    
            else:
                log_message("No last comand found for: " + curr_item)

            mqtt_last_cmd[curr_item] = new_last_cmd_value
            log_message("New last comand for %s: %s" % (mqtt_last_cmd[curr_item], new_last_cmd_value))         

        except Exception as e :
            log_message("Stop comand check was unsuccessful: " + str(e))
            return

        # prepare comand
        try:
            send_comand = "%s/%s/%s" % (hp_host, hp_devices_url_cmd_part, curr_item)     

            #is integer position
            if is_integer(message.payload):
                if int(message.payload) >= 0 and int(message.payload) <= 100 :    
                    send_data = json.loads(hp_send_data_gotopos_tmpl)     
                    send_data["value"] = message.payload            

            #is stop comand            
            elif str(message.payload) == "STOP":
                print("message is stop")
                send_data = json.loads(hp_send_data_stop_tmpl)  
            
            else:
                log_message("No valid comand found: %s" % (message.payload))

        except Exception as e :
            log_message("Error during comand creation: %s" % str(e))
            return

        # send comand        
        try:   
            log_message("Try to send : " + send_comand + " with " + json.dumps(send_data))
            response = requests.put(send_comand, json.dumps(send_data), headers=headers)             

        except Exception as e :
            log_message("Request to HomePilot was unsuccessful: " + str(e))
            return

        parsed_json = json.loads(response.text)            
        log_message(parsed_json["error_description"])

# main
#variables
headers = {"Content-Type": "application/json"}
cfg_file_name = "data/hp2mqtt.yaml"
log_file_name = "log/hp2mqtt.log"
dev_file_name = "data/device_info.json"

mqtt_connected = False
mqtt_broker_address= "localhost"
mqtt_port = 1883
mqtt_user = ""
mqtt_password = ""
mqtt_channel = "hp2mqtt"
mqtt_items = {}
mqtt_last_cmd = {}

hp_host = "http://"
hp_devices_url_cmd_part = "devices"
hp_devices_url_list_part = "v4/devices"
hp_send_data_gotopos_tmpl = '{"name": "GOTO_POS_CMD", "value": "0"}'
hp_send_data_stop_tmpl = '{"name": "STOP_CMD"}'

# delete log file
log_file = open(log_file_name, "w")
atexit.register(close_logfile)

# read configuration file
try:
    with open(cfg_file_name) as file:
        config_dict = yaml.safe_load(file)

        # system settyings
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
        
        if config_dict_sys.get("hp_host"): 
          hp_host = hp_host + config_dict_sys["hp_host"]

        # devices
        mqtt_items = config_dict["devices"]
        
        log_message("Configuration loaded incl. following items: " + str(mqtt_items))


except Exception as e:
    log_message("Error while reading configuration file %s: %s" % (cfg_file_name, str(e)))
    raise SystemExit(e)

# get device list if requested via startup paramter -d
if len(sys.argv) > 1:
    if sys.argv[1] == "-d":
        log_message("Get HomePilot device list: " + hp_host)
        try:
            response = requests.get("%s/%s" % (hp_host, hp_devices_url_list_part))
                
            log_message("Connection established successfully")
            parsed_json = (json.loads(response.text))
            log_message(json.dumps(parsed_json, indent=4, sort_keys=True))

            device_info_file = open(dev_file_name, "w")
            # issue with encoding device_info_file.write(response.text)
            device_info_file.close
            log_message("File %2 update with current device list." % (dev_file_name))
            sys.exit(0)

        except requests.exceptions.RequestException as e:
            log_message("Could not connect to HomePilot at %s. Please check if IP and Login is valid. %s" % (hp_host, str(e)))
            raise SystemExit(e)

        except Exception as e:
            log_message("Error during device investigation: " + str(e))
            raise SystemExit(e)
        

# initiate mqtt listener
client = mqttClient.Client()               
client.username_pw_set(mqtt_user, mqtt_password)    
client.on_connect= on_connect                      
client.on_message= on_set_message                      

client.connect(mqtt_broker_address, mqtt_port)  
client.loop_start()                        

while mqtt_connected != True:    
    time.sleep(0.1)

client.subscribe(mqtt_channel + "/#" )
log_message("Listen to "+ mqtt_channel + "/#")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    log_message("exiting")
    client.disconnect()
    client.loop_stop()
