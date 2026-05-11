import os
import cv2
import csv
import numpy as np
import zenoh
from datetime import datetime
import threading
import time


# ===== Zenoh setup =====
KEY_EXPR = "office/pi1/image"
LISTEN_ENDPOINT = "tcp/0.0.0.0:7447"

output_base = "./analyzed_images_zenoh"
os.makedirs(output_base, exist_ok=True)

RUN_AFTER_FIRST_IMAGE = 10
NUMBER_OF_LOOPS = 1

csv_file = "zenoh_receiver_results.csv"

timer_started = False
saved_count = 0
stop_event = threading.Event()
lock = threading.Lock()

all_loop_results = []


def stop_after_10_seconds():
    time.sleep(RUN_AFTER_FIRST_IMAGE)
    print("\n⏱️ 10 seconds completed after first image. Stopping receiver...")
    stop_event.set()


def on_sample(sample):
    global timer_started, saved_count

    try:
        with lock:
            if not timer_started:
                timer_started = True
                print("🟢 First image received. 10-second counter started.")
                threading.Thread(
                    target=stop_after_10_seconds,
                    daemon=True
                ).start()

        print(f"📥 Sample received on key: {sample.key_expr}")

        # Your sender sends RAW JPEG bytes
        jpeg_bytes = bytes(sample.payload)

        np_arr = np.frombuffer(jpeg_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            print("❌ Could not decode image.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"zenoh_image_{timestamp}.jpg"
        save_path = os.path.join(output_base, filename)

        cv2.imwrite(save_path, image)

        with lock:
            saved_count += 1

        print(f"✅ Image saved: {save_path}")

    except Exception as e:
        print(f"❌ Error processing image: {e}")


def folder_stats_and_delete(folder):
    image_exts = (".jpg", ".jpeg", ".png")

    image_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(image_exts)
    ]

    total_images = len(image_files)
    total_size_bytes = sum(os.path.getsize(f) for f in image_files)
    total_size_mb = total_size_bytes / 1024 / 1024

    images_per_sec = total_images / RUN_AFTER_FIRST_IMAGE
    mb_per_sec = total_size_mb / RUN_AFTER_FIRST_IMAGE

    print("\n📊 Loop Results")
    print(f"Total images in folder: {total_images}")
    print(f"Total folder image size: {total_size_mb:.1f} MB")
    print(f"Images per second: {images_per_sec:.2f}")
    print(f"MB per second: {mb_per_sec:.2f}")

    for f in image_files:
        os.remove(f)

    print("🗑️ All images deleted.")

    return total_images, total_size_mb, images_per_sec, mb_per_sec


def write_csv_results(results):
    if not results:
        return

    total_loops = len(results)

    avg_images = sum(r["total_images"] for r in results) / total_loops
    avg_mb = sum(r["total_size_mb"] for r in results) / total_loops
    avg_images_per_sec = sum(r["images_per_sec"] for r in results) / total_loops
    avg_mb_per_sec = sum(r["mb_per_sec"] for r in results) / total_loops

    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "loop_number",
            "run_duration_seconds",
            "total_images",
            "total_size_mb",
            "images_per_second",
            "mb_per_second",
            "timestamp"
        ])

        for r in results:
            writer.writerow([
                r["loop_number"],
                r["run_duration_seconds"],
                r["total_images"],
                f"{r['total_size_mb']:.1f}",
                f"{r['images_per_sec']:.2f}",
                f"{r['mb_per_sec']:.2f}",
                r["timestamp"]
            ])

        writer.writerow([])
        writer.writerow(["AVERAGE"])
        writer.writerow([
            "average_images_per_loop",
            "average_mb_per_loop",
            "average_images_per_second",
            "average_mb_per_second"
        ])
        writer.writerow([
            f"{avg_images:.2f}",
            f"{avg_mb:.1f}",
            f"{avg_images_per_sec:.2f}",
            f"{avg_mb_per_sec:.2f}"
        ])

    print(f"\n💾 CSV results saved to: {csv_file}")


for loop_number in range(1, NUMBER_OF_LOOPS + 1):
    print("\n==============================")
    print(f"🚀 Starting Zenoh loop {loop_number}/{NUMBER_OF_LOOPS}")
    print("==============================")

    timer_started = False
    saved_count = 0
    stop_event.clear()

    print(f"🚀 Starting Zenoh listener on {LISTEN_ENDPOINT}")

    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    conf.insert_json5("listen/endpoints", f'["{LISTEN_ENDPOINT}"]')

    session = zenoh.open(conf)

    print("✅ Zenoh session opened.")
    print(f"📡 Subscribing to key expression: {KEY_EXPR}")

    subscriber = session.declare_subscriber(KEY_EXPR, on_sample)

    try:
        while not stop_event.is_set():
            time.sleep(0.1)

    finally:
        subscriber.undeclare()
        session.close()
        print("🔌 Zenoh session closed.")

    total_images, total_size_mb, images_per_sec, mb_per_sec = folder_stats_and_delete(output_base)

    loop_result = {
        "loop_number": loop_number,
        "run_duration_seconds": RUN_AFTER_FIRST_IMAGE,
        "total_images": total_images,
        "total_size_mb": total_size_mb,
        "images_per_sec": images_per_sec,
        "mb_per_sec": mb_per_sec,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    all_loop_results.append(loop_result)

    print(f"✅ Loop {loop_number}/{NUMBER_OF_LOOPS} completed.")


write_csv_results(all_loop_results)

print("\n🎉 All Zenoh loops completed. Script terminated.")
