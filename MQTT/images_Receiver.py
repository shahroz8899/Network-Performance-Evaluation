import os
import cv2
import base64
import numpy as np
import paho.mqtt.client as mqtt
from datetime import datetime
import threading
import time

# MQTT and folder setup
broker = '192.168.1.135'
port = 1883
output_base = './analyzed_images'
os.makedirs(output_base, exist_ok=True)

RUN_AFTER_FIRST_IMAGE = 10  # seconds

timer_started = False
saved_count = 0
lock = threading.Lock()


def stop_after_10_seconds(client):
    time.sleep(RUN_AFTER_FIRST_IMAGE)
    print("\n⏱️ 10 seconds completed after first image. Stopping receiver...")
    client.disconnect()


def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to MQTT broker with result code {rc}")
    client.subscribe("images/#")


def on_message(client, userdata, msg):
    global timer_started, saved_count

    try:
        with lock:
            if not timer_started:
                timer_started = True
                print("🟢 First image received. 10-second counter started.")
                threading.Thread(
                    target=stop_after_10_seconds,
                    args=(client,),
                    daemon=True
                ).start()

        print(f"📥 Message received on topic: {msg.topic}")

        image_data = base64.b64decode(msg.payload)
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            print("❌ Could not decode image.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        topic_id = msg.topic.split("/")[-1]
        filename = f"{topic_id}_{timestamp}.jpg"
        save_path = os.path.join(output_base, filename)

        cv2.imwrite(save_path, image)

        with lock:
            saved_count += 1

        print(f"✅ Image saved: {save_path}")

    except Exception as e:
        print(f"❌ Error processing image: {e}")


def folder_stats_and_delete(folder):
    image_exts = ('.jpg', '.jpeg', '.png')

    image_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(image_exts)
    ]

    total_size_bytes = sum(os.path.getsize(f) for f in image_files)
    total_size_mb = total_size_bytes / 1024 / 1024

    print("\n📊 Final Results")
    print(f"Total images in folder: {len(image_files)}")
    print(f"Total folder image size: {total_size_mb:.1f} MB")

    for f in image_files:
        os.remove(f)

    print("🗑️ All images deleted.")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("🚀 Connecting to MQTT broker...")
client.connect(broker, port, 60)

try:
    client.loop_forever()
finally:
    folder_stats_and_delete(output_base)
    print("✅ Script terminated.")
