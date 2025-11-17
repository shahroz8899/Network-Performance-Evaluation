import os
import logging
import paho.mqtt.client as mqtt
import time
import base64
import cv2

# ===== Configuration =====
broker = '192.168.1.68'  # Pi1 IP
port = 1883
TOPIC_BASE = 'images/pi1'
qos_level = 1

# Total topics per image (including the base one): pi1, pi1_1 ... pi1_(REPLICAS-1)
REPLICAS = 1

# Publish the same encoded image this many times per topic (set 10, 20, 30, ...)
MULTIPLY_FACTOR = 8

# Run script for a custom duration (in seconds)
RUN_DURATION = 60  # <-- Change this (e.g., 30, 120, 300 seconds, etc.)

# Save to disk only at the end (toggle off later if you want no saving at all)
SAVE_TO_DISK = False

image_counter_file = 'image_counter.txt'
processed_folder = 'received_images'

# ===== Logging =====
logging.basicConfig(
    filename='image_capture_mqtt.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# ===== MQTT Callbacks =====
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info(f"Connected to broker {broker}:{port} with result code {rc}")
        print(f"Connected to broker {broker}:{port} with result code {rc}")
    else:
        logging.error(f"Failed to connect to broker {broker}:{port} with result code {rc}")
        print(f"Failed to connect to broker {broker}:{port} with result code {rc}")

def on_publish(client, userdata, mid):
    logging.info(f"Message published with mid {mid}")


# ===== Topic builder =====
def build_topics(base: str, replicas: int):
    if replicas <= 0:
        return []
    return [base] + [f"{base}_{i}" for i in range(1, replicas)]

# ===== Counter utilities =====
def get_next_image_number(counter_file):
    try:
        with open(counter_file, 'r') as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return 1

def update_image_number(counter_file, number):
    with open(counter_file, 'w') as file:
        file.write(str(number))
        
# ===== Main =====
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish

    logging.info(f"Connecting to broker {broker}:{port}")
    try:
        client.connect(broker, port, 60)
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        print(f"Connection failed: {e}")
        return

    client.loop_start()

    # Initialize camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.1)  # warmup

    start_time = time.time()
    try:
        while True:
            # Check time limit
            elapsed_time = time.time() - start_time
            if elapsed_time > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                logging.info(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                break

            loop_t0 = time.time()
            image_number = get_next_image_number(image_counter_file)
            filename = f"image_{image_number:04d}.jpg"

            # 1) Capture once
            t1 = time.time()
            ret, frame = cap.read()
            if not ret:
                logging.error("Failed to read from camera")
                time.sleep(0.1)
                continue
            t2 = time.time()
            logging.info(f"Capture time: {t2 - t1:.4f}s")

            # 2) Encode once (in-memory)
            t3 = time.time()
            ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                logging.error("JPEG encoding failed")
                time.sleep(0.8)
                continue
            jpeg_bytes = buf.tobytes()
            payload_b64 = base64.b64encode(jpeg_bytes).decode()
            t4 = time.time()
            logging.info(f"Encode + B64 time: {t4 - t3:.4f}s")

            # 3) Publish to a list of topics, repeated MULTIPLY_FACTOR times
            topics = build_topics(TOPIC_BASE, REPLICAS)
            pub_t0 = time.time()
            total_publishes = 0
            for t in topics:
                for i in range(MULTIPLY_FACTOR):
                    result = client.publish(t, payload_b64, qos=qos_level)
                    total_publishes += 1
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logging.info(
                            f"Published copy {i+1}/{MULTIPLY_FACTOR} of {filename} to '{t}' (mid={result.mid})"
                        )
                    else:
                        logging.error(
                            f"Publish failed (copy {i+1}/{MULTIPLY_FACTOR}) to '{t}' rc={result.rc}"
                        )
            pub_t1 = time.time()
            logging.info(
                f"Publish (all topics x{MULTIPLY_FACTOR}) count={total_publishes} time: {pub_t1 - pub_t0:.4f}s"
            )

            # 4) Save once at the end (optional)
            if SAVE_TO_DISK:
                try:
                    os.makedirs(processed_folder, exist_ok=True)
                    out_path = os.path.join(processed_folder, filename)
                    with open(out_path, 'wb') as f:
                        f.write(jpeg_bytes)
                    logging.info(f"Saved image once at end: {out_path}")
                except Exception as e:
                    logging.error(f"Failed to save image at end: {e}")

            # 5) Update counter (we processed this capture regardless of save)
            update_image_number(image_counter_file, image_number + 1)

            logging.info(f"Total loop time: {time.time() - loop_t0:.4f}s")
            time.sleep(0.01)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected. Stopping the script.")
    except Exception as e:
        logging.error(f"Unexpected error occurred: {e}")
        print(f"Unexpected error occurred: {e}")
    finally:
        cap.release()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
