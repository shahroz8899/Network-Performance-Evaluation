import os
import logging
import time
import cv2
import zenoh
import json

# ===== Configuration =====
KEY_BASE = "office/pi1/image"

REPLICAS = 1
MULTIPLY_FACTOR = 10
RUN_DURATION = 10000

SAVE_TO_DISK = False
processed_folder = "sent_images"
image_counter_file = "image_counter.txt"

# ===== Worker IPs =====
WORKER_IPS = [
    "192.168.1.21",   # Worker 1 IP
    "192.168.1.22"    # Worker 2 IP
]

WORKER_PORT = 7447

# ===== Logging =====
logging.basicConfig(
    filename="image_capture_zenoh.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s"
)


def build_keys(base: str, replicas: int):
    if replicas <= 0:
        return []
    return [base] + [f"{base}_{i}" for i in range(1, replicas)]


def get_next_image_number(counter_file):
    try:
        with open(counter_file, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return 1


def update_image_number(counter_file, number):
    with open(counter_file, "w") as file:
        file.write(str(number))


def main():
    endpoints = [f"tcp/{ip}:{WORKER_PORT}" for ip in WORKER_IPS]

    print("[Zenoh] Connecting to workers:")
    for ep in endpoints:
        print(f"  - {ep}")

    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    conf.insert_json5("connect/endpoints", json.dumps(endpoints))

    session = zenoh.open(conf)

    keys = build_keys(KEY_BASE, REPLICAS)
    publishers = {}

    for k in keys:
        publishers[k] = session.declare_publisher(k)
        print(f"[Zenoh] Publisher declared on key: {k}")

    os.makedirs(processed_folder, exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.1)

    if not cap.isOpened():
        print("[ERROR] Camera could not be opened")
        session.close()
        return

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                break

            loop_start = time.time()

            image_number = get_next_image_number(image_counter_file)
            filename = f"image_{image_number:04d}.jpg"

            t1 = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Frame capture failed")
                continue
            t2 = time.time()

            ok, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 95]
            )

            if not ok:
                print("[ERROR] JPEG encoding failed")
                continue

            jpeg_bytes = buf.tobytes()
            t3 = time.time()

            total_publishes = 0

            for key, pub in publishers.items():
                for _ in range(MULTIPLY_FACTOR):
                    pub.put(jpeg_bytes)
                    total_publishes += 1

            t4 = time.time()

            if SAVE_TO_DISK:
                try:
                    out_path = os.path.join(processed_folder, filename)
                    with open(out_path, "wb") as f:
                        f.write(jpeg_bytes)
                except Exception as e:
                    print(f"[ERROR] Failed to save image locally: {e}")

            update_image_number(image_counter_file, image_number + 1)

            print(
                f"Publishes: {total_publishes} | "
                f"Capture: {t2 - t1:.4f}s | "
                f"Encode: {t3 - t2:.4f}s | "
                f"Publish: {t4 - t3:.4f}s | "
                f"Total loop: {t4 - loop_start:.4f}s"
            )

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        cap.release()

        for pub in publishers.values():
            try:
                pub.undeclare()
            except Exception:
                pass

        session.close()
        print("Zenoh session closed.")


if __name__ == "__main__":
    main()
