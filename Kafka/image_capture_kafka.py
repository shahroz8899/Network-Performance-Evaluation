import os
import logging
import time
import base64
import json
import cv2
from kafka import KafkaProducer

# ===== Configuration =====
KAFKA_BOOTSTRAP = "192.168.1.176:9092"  # <-- change to your broker:port
TOPIC_BASE = "images_pi1"
REPLICAS = 1               # same semantics as in your HTTP/MQTT version
MULTIPLY_FACTOR = 20       # how many times to send the same image per topic
RUN_DURATION = 10          # seconds to run
SAVE_TO_DISK = False       # optional (same idea as before)

image_counter_file = "image_counter.txt"
processed_folder = "received_images"

# ===== Logging =====
logging.basicConfig(
    filename="image_capture_kafka.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s"
)

# ===== Topic builder (same as your HTTP/MQTT) =====
def build_topics(base: str, replicas: int):
    if replicas <= 0:
        return []
    return [base] + [f"{base}_{i}" for i in range(1, replicas)]

# ===== Counter utilities =====
def get_next_image_number(counter_file):
    try:
        with open(counter_file, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 1

def update_image_number(counter_file, number):
    with open(counter_file, "w") as f:
        f.write(str(number))

def main():
    # Initialize camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.1)  # warmup

    # Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=1,
        linger_ms=5,
        acks="all",
    )

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

            # 2) Encode once (JPEG) + Base64 (to match your HTTP payload)
            t3 = time.time()
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                logging.error("JPEG encoding failed")
                time.sleep(0.8)
                continue
            jpeg_bytes = buf.tobytes()
            payload_b64 = base64.b64encode(jpeg_bytes).decode("ascii")
            t4 = time.time()
            logging.info(f"Encode + B64 time: {t4 - t3:.4f}s")

            # 3) Build topics and send over Kafka
            topics = build_topics(TOPIC_BASE, REPLICAS)
            total_msgs = 0
            kaf_t0 = time.time()

            for t in topics:
                for i in range(MULTIPLY_FACTOR):
                    msg = {
                        "topic": t,            # carried for parity with your HTTP receiver
                        "filename": filename,  # optional; nice for logs/saving
                        "image_b64": payload_b64
                    }
                    try:
                        producer.send(t, value=msg)
                        total_msgs += 1
                        logging.info(
                            f"Kafka SEND {i+1}/{MULTIPLY_FACTOR} of {filename} to topic '{t}'"
                        )
                    except Exception as e:
                        logging.error(
                            f"Kafka SEND exception ({i+1}/{MULTIPLY_FACTOR}) to topic '{t}': {e}"
                        )

            # force a batch flush periodically
            producer.flush()
            kaf_t1 = time.time()
            logging.info(
                f"Kafka SEND (all topics x{MULTIPLY_FACTOR}) count={total_msgs} "
                f"time: {kaf_t1 - kaf_t0:.4f}s"
            )

            # 4) Optional: save the captured image locally
            if SAVE_TO_DISK:
                try:
                    os.makedirs(processed_folder, exist_ok=True)
                    out_path = os.path.join(processed_folder, filename)
                    with open(out_path, "wb") as f:
                        f.write(jpeg_bytes)
                    logging.info(f"Saved image once at end: {out_path}")
                except Exception as e:
                    logging.error(f"Failed to save image at end: {e}")

            # 5) Update counter and loop pacing
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
        try:
            producer.flush(5)
        except Exception:
            pass

if __name__ == "__main__":
    main()
