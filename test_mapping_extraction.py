import paho.mqtt.client as mqtt
import json
import time

BROKER_IP = "192.168.5.27"  # Replace with your broker's IP
BROKER_PORT = 1883
TOPIC = "send_flow_mappings"

# Load the flow_mappings.json file
with open("flow_mappings.json", "r") as file:
    flow_mappings = json.load(file)

# Define the MQTT client
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        # Publish the flow_mappings.json content
        client.publish(TOPIC, json.dumps(flow_mappings))
        print(f"Published flow mappings to topic '{TOPIC}'")
    else:
        print(f"Failed to connect, return code {rc}")

# Set up the client and connect
client.on_connect = on_connect
client.connect(BROKER_IP, BROKER_PORT, 60)

# Start the loop to process network traffic
client.loop_start()
time.sleep(2)  # Allow time for the message to be sent
client.loop_stop()
client.disconnect()