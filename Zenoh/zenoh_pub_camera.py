import os
import logging
import time
import cv2
import zenoh

# ===== Configuration =====
# Zenoh key base (similar to topic in MQTT)
KEY_BASE = "office/pi1/image" # We can choose any KEY

# Total keys per image (including the base one): pi1, pi1_1 ... pi1_(REPLICAS-1)
REPLICAS = 1

# Publish the same encoded image this many times per key (like your MQTT MULTIPLY_FACTOR)
MULTIPLY_FACTOR = 15

# Run script for a custom duration (in seconds)
RUN_DURATION = 10  # <-- Change this (e.g., 30, 120, 300 seconds, etc.)

# Save to disk only at the end (optional)
SAVE_TO_DISK = True
processed_folder = "sent_images"

image_counter_file = "image_counter.txt"

# ===== Logging =====
logging.basicConfig(
    filename="image_capture_zenoh.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s"
)


# ===== Key builder (similar to MQTT topics) =====
def build_keys(base: str, replicas: int):
    if replicas <= 0:
        return []
    return [base] + [f"{base}_{i}" for i in range(1, replicas)]


# ===== Counter utilities =====
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
    # ===== Zenoh configuration =====
    WORKER_IP = "192.168.1.#"   # <-- your worker node IP

    print(f"[Zenoh] Connecting to worker @ {WORKER_IP}:7447 ...")

    # Create Zenoh config
    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    conf.insert_json5("connect/endpoints", f'["tcp/{WORKER_IP}:7447"]')

    # Open Zenoh session
    session = zenoh.open(conf)

    # Declare publishers for all replicas
    keys = build_keys(KEY_BASE, REPLICAS)
    publishers = {}
    for k in keys:
        publishers[k] = session.declare_publisher(k)
        print(f"[Zenoh] Publisher declared on key: {k}")

    # Ensure local save folder exists (for SAVE_TO_DISK)
    os.makedirs(processed_folder, exist_ok=True)

    # ===== Camera Init =====
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.1)

    if not cap.isOpened():
        print("[ERROR] Camera could not be opened")
        return

   # ===== Timing Setup =====
    start_time = time.time()

    # ===== Publish Loop =====
    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                break

            loop_start = time.time()

            # Get next image number (for local saving)
            image_number = get_next_image_number(image_counter_file)
            filename = f"image_{image_number:04d}.jpg"

            # --- Capture ---
            t1 = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Frame capture failed")
                continue
            t2 = time.time()

            # --- JPEG Encode ---
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                print("[ERROR] JPEG encoding failed")
                continue
            jpeg_bytes = buf.tobytes()
            t3 = time.time()

            # --- Publish raw bytes to all keys, MULTIPLY_FACTOR times ---
            total_publishes = 0
            for key, pub in publishers.items():
                for i in range(MULTIPLY_FACTOR):
                    pub.put(jpeg_bytes)
                    total_publishes += 1

            t4 = time.time()

            # --- Optionally save one copy locally on the Pi ---
            if SAVE_TO_DISK:
                try:
                    out_path = os.path.join(processed_folder, filename)
                    with open(out_path, "wb") as f:
                        f.write(jpeg_bytes)
                except Exception as e:
                    print(f"[ERROR] Failed to save image locally: {e}")

            # Update image counter
            update_image_number(image_counter_file, image_number + 1)

            # Print timing
            print(
                f"Publishes: {total_publishes} | "
                f"Capture: {t2 - t1:.4f}s | Encode: {t3 - t2:.4f}s | "
                f"Publish: {t4 - t3:.4f}s | Total loop: {t4 - loop_start:.4f}s"
            )

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        cap.release()
        for pub in publishers.values():
            pub.undeclare()
        session.close()
        print("Zenoh session closed.")

if __name__ == "__main__":
    main()

