import os
import cv2
import base64
import json
import numpy as np
from datetime import datetime
from queue import Queue
import threading
from kafka import KafkaConsumer

# ===== Configuration =====
KAFKA_BOOTSTRAP = "localhost:9092"  # <-- change to your broker:port
# Subscribe pattern: the base topic and its _replicas
TOPIC_BASE = "images_pi1"
REPLICAS = 1   # must match the sender if you want the additional topics
# If you prefer explicit list rather than pattern, set BUILD_EXPLICIT_TOPICS=True
BUILD_EXPLICIT_TOPICS = True

# Folder setup (same as your HTTP receiver)
output_base = "./analyzed_images"
os.makedirs(output_base, exist_ok=True)

# Thread-safe queue to hold messages (topic_name, image_b64, filename)
msg_queue = Queue()

# ===== Helpers =====
def build_topics(base: str, replicas: int):
    if replicas <= 0:
        return []
    return [base] + [f"{base}_{i}" for i in range(1, replicas)]

def topic_id_for_filename(topic_name: str):
    # Mimic your HTTP receiver’s topic extraction for filenames
    return topic_name.split("/")[-1]

# ===== Background worker =====
def image_worker():
    while True:
        topic_name, image_b64, filename_hint = msg_queue.get()

        try:
            image_data = base64.b64decode(image_b64)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                print("❌ Could not decode image.")
                continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            topic_id = topic_id_for_filename(topic_name)
            # Preserve your naming pattern: <topic_last_part>_<timestamp>.jpg
            out_filename = f"{topic_id}_{timestamp}.jpg"
            save_path = os.path.join(output_base, out_filename)

            cv2.imwrite(save_path, image)
            print(f"✅ Image saved: {save_path}")

        except Exception as e:
            print(f"❌ Error processing image: {e}")

# Start worker thread
threading.Thread(target=image_worker, daemon=True).start()

def main():
    if BUILD_EXPLICIT_TOPICS:
        topics = build_topics(TOPIC_BASE, REPLICAS)
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id="image-receiver-group",
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        print(f"🚀 Kafka image receiver subscribed to topics: {topics}")
    else:
        # Example of pattern subscription (if your broker supports regex subscription via kafka-python)
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id="image-receiver-group",
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        topic_pattern = f"{TOPIC_BASE}.*"
        consumer.subscribe(pattern=topic_pattern)
        print(f"🚀 Kafka image receiver subscribed to pattern: {topic_pattern}")

    print("    Send JSON messages with keys: topic, filename, image_b64")

    for record in consumer:
        try:
            payload = record.value or {}
            # Prefer Kafka record.topic for the canonical topic name
            topic_name = record.topic
            # If sender included "topic" in payload, keep it for parity/logging
            topic_name_payload = payload.get("topic")
            if topic_name_payload and topic_name_payload != topic_name:
                # Not required, just a heads-up if they diverge
                print(f"ℹ️ Payload topic='{topic_name_payload}' vs Kafka topic='{topic_name}'")

            filename = payload.get("filename", "unknown.jpg")
            image_b64 = payload.get("image_b64")

            if image_b64 is None:
                print("❌ Missing image_b64 in message; skipping.")
                continue

            msg_queue.put((topic_name, image_b64, filename))

        except Exception as e:
            print(f"❌ Error handling Kafka message: {e}")

if __name__ == "__main__":
    main()
