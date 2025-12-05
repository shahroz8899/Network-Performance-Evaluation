import os
import logging
import time
import base64
import cv2
import requests  # <--- HTTP client

# ===== Configuration =====
# HTTP server (receiver) address on your LAN
HTTP_SERVER = "http://192.168.1.176:8000/upload"  # <-- change IP/port if needed

TOPIC_BASE = 'images/pi1'
REPLICAS = 1              # same meaning as in MQTT version
MULTIPLY_FACTOR = 20       # how many times to send the same image per topic
RUN_DURATION = 10         # seconds to run
SAVE_TO_DISK = False      # optional, same idea as before

image_counter_file = 'image_counter.txt'
processed_folder = 'received_images'

# ===== Logging =====
logging.basicConfig(
    filename='image_capture_http.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# ===== Topic builder (same as MQTT) =====
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

            # 2) Encode once (in-memory) + Base64 (same as MQTT)
            t3 = time.time()
            ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                logging.error("JPEG encoding failed")
                time.sleep(0.8)
                continue
            jpeg_bytes = buf.tobytes()
            payload_b64 = base64.b64encode(jpeg_bytes).decode('ascii')
            t4 = time.time()
            logging.info(f"Encode + B64 time: {t4 - t3:.4f}s")

            # 3) Build topics and send over HTTP
            topics = build_topics(TOPIC_BASE, REPLICAS)
            total_posts = 0
            http_t0 = time.time()
            
            for t in topics:
                for i in range(MULTIPLY_FACTOR):
                    json_payload = {
                        "topic": t,
                        "filename": filename,
                        "image_b64": payload_b64
                    }

                    try:
                        resp = requests.post(HTTP_SERVER, json=json_payload, timeout=5)
                        total_posts += 1
                        if resp.status_code == 200:
                            logging.info(
                                f"HTTP POST {i+1}/{MULTIPLY_FACTOR} of {filename} to topic '{t}' "
                                f"status={resp.status_code}"
                            )
                        else:
                            logging.error(
                                f"HTTP POST failed ({i+1}/{MULTIPLY_FACTOR}) to topic '{t}' "
                                f"status={resp.status_code}, body={resp.text}"
                            )
                    except Exception as e:
                        logging.error(
                            f"HTTP POST exception ({i+1}/{MULTIPLY_FACTOR}) to topic '{t}': {e}"
                        )

            http_t1 = time.time()
            logging.info(
                f"HTTP POST (all topics x{MULTIPLY_FACTOR}) count={total_posts} "
                f"time: {http_t1 - http_t0:.4f}s"
            )
            
            # 4) Optional: save the captured image locally (like MQTT version)
            if SAVE_TO_DISK:
                try:
                    os.makedirs(processed_folder, exist_ok=True)
                    out_path = os.path.join(processed_folder, filename)
                    with open(out_path, 'wb') as f:
                        f.write(jpeg_bytes)
                    logging.info(f"Saved image once at end: {out_path}")
                except Exception as e:
                    logging.error(f"Failed to save image at end: {e}")

            # 5) Update counter
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


if __name__ == "__main__":
    main()
