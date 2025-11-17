import os
import cv2
import base64
import numpy as np
import paho.mqtt.client as mqtt
from datetime import datetime
from queue import Queue
import threading

# MQTT and folder setup
broker = '192.168.1.68'  # Since Mosquitto broker is now running on the master node
port = 1883
output_base = './analyzed_images'
os.makedirs(output_base, exist_ok=True)

# Thread-safe queue to hold messages
msg_queue = Queue()

# Background worker to decode and save images
def image_worker():
    while True:
        topic, payload = msg_queue.get()

        try:
            image_data = base64.b64decode(payload)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                print("❌ Could not decode image.")
                continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            topic_id = topic.split("/")[-1]
            filename = f"{topic_id}_{timestamp}.jpg"
            save_path = os.path.join(output_base, filename)

            cv2.imwrite(save_path, image)
            print(f"✅ Image saved: {save_path}")

        except Exception as e:
            print(f"❌ Error processing image: {e}")

# Start the background image worker thread
threading.Thread(target=image_worker, daemon=True).start()

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to MQTT broker with result code {rc}")
    client.subscribe("images/#")

def on_message(client, userdata, msg):
    # Just queue the message for processing
    msg_queue.put((msg.topic, msg.payload))

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("🚀 Connecting to local MQTT broker on master...")
client.connect(broker, port, 60)
client.loop_forever()
