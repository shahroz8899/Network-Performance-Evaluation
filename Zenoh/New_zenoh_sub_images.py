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
NUMBER_OF_LOOPS = 50
FIRST_IMAGE_TIMEOUT = 60

csv_file = "zenoh_receiver_results.csv"

lock = threading.Lock()
callbacks_done = threading.Condition(lock)

receiver_active = False
timer_started = False
loop_start_time = None
active_callbacks = 0

all_loop_results = []


def on_sample(sample):
    global timer_started, loop_start_time, active_callbacks

    with lock:
        if not receiver_active:
            return

        active_callbacks += 1

        if not timer_started:
            timer_started = True
            loop_start_time = time.time()
            print(f"🟢 First image received. {RUN_AFTER_FIRST_IMAGE}-second counter started.")

    try:
        with lock:
            if not receiver_active:
                return

        jpeg_bytes = bytes(sample.payload)
        np_arr = np.frombuffer(jpeg_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            print("❌ Could not decode image.")
            return

        with lock:
            if not receiver_active:
                return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"zenoh_image_{timestamp}.jpg"
        save_path = os.path.join(output_base, filename)

        cv2.imwrite(save_path, image)

    except Exception as e:
        print(f"❌ Error processing image: {e}")

    finally:
        with lock:
            active_callbacks -= 1
            if active_callbacks == 0:
                callbacks_done.notify_all()


def wait_for_callbacks_to_finish():
    with lock:
        while active_callbacks > 0:
            callbacks_done.wait(timeout=0.5)


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
            "timestamp",
            "status"
        ])

        for r in results:
            writer.writerow([
                r["loop_number"],
                r["run_duration_seconds"],
                r["total_images"],
                f"{r['total_size_mb']:.1f}",
                f"{r['images_per_sec']:.2f}",
                f"{r['mb_per_sec']:.2f}",
                r["timestamp"],
                r["status"]
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

    print(f"💾 CSV results saved/updated: {csv_file}")


def main():
    global receiver_active, timer_started, loop_start_time, active_callbacks

    print(f"🚀 Starting Zenoh listener ONCE on {LISTEN_ENDPOINT}")

    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    conf.insert_json5("listen/endpoints", f'["{LISTEN_ENDPOINT}"]')

    session = zenoh.open(conf)
    print("✅ Zenoh session opened.")

    subscriber = session.declare_subscriber(KEY_EXPR, on_sample)
    print(f"📡 Subscribed to key expression: {KEY_EXPR}")

    try:
        for loop_number in range(1, NUMBER_OF_LOOPS + 1):
            print("\n==============================")
            print(f"🚀 Starting Zenoh loop {loop_number}/{NUMBER_OF_LOOPS}")
            print("==============================")

            with lock:
                receiver_active = True
                timer_started = False
                loop_start_time = None
                active_callbacks = 0

            wait_start = time.time()

            while True:
                with lock:
                    started = timer_started
                    start_time_copy = loop_start_time

                if started:
                    break

                if time.time() - wait_start > FIRST_IMAGE_TIMEOUT:
                    print(f"⚠️ No image received within {FIRST_IMAGE_TIMEOUT} seconds.")
                    break

                time.sleep(0.01)

            if timer_started:
                while True:
                    with lock:
                        elapsed = time.time() - loop_start_time

                    if elapsed >= RUN_AFTER_FIRST_IMAGE:
                        break

                    time.sleep(0.01)

                print(f"\n⏱️ {RUN_AFTER_FIRST_IMAGE} seconds completed after first image. Stopping loop...")

            with lock:
                receiver_active = False

            wait_for_callbacks_to_finish()

            total_images, total_size_mb, images_per_sec, mb_per_sec = folder_stats_and_delete(output_base)

            status = "success" if total_images > 0 else "no_images_received"

            loop_result = {
                "loop_number": loop_number,
                "run_duration_seconds": RUN_AFTER_FIRST_IMAGE,
                "total_images": total_images,
                "total_size_mb": total_size_mb,
                "images_per_sec": images_per_sec,
                "mb_per_sec": mb_per_sec,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": status
            }

            all_loop_results.append(loop_result)

            write_csv_results(all_loop_results)

            print(f"✅ Loop {loop_number}/{NUMBER_OF_LOOPS} completed.")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        write_csv_results(all_loop_results)

    finally:
        print("\n🔌 Closing Zenoh only once after all loops...")

        try:
            subscriber.undeclare()
        except Exception as e:
            print(f"⚠️ Error undeclaring subscriber: {e}")

        try:
            session.close()
        except Exception as e:
            print(f"⚠️ Error closing Zenoh session: {e}")

        write_csv_results(all_loop_results)

        print("✅ Zenoh session closed.")
        print("🎉 Receiver script terminated.")


if __name__ == "__main__":
    main()
