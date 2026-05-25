import os
import cv2
import base64
import json
import csv
import numpy as np
from datetime import datetime
from queue import Queue
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


# ===== HTTP Receiver Configuration =====
HOST = "0.0.0.0"
PORT = 8000

# ===== Benchmark Configuration =====
output_base = "./analyzed_images_http"
os.makedirs(output_base, exist_ok=True)

RUN_AFTER_FIRST_IMAGE = 10
NUMBER_OF_LOOPS = 50
FIRST_IMAGE_TIMEOUT = 60

csv_file = "http_receiver_results.csv"

# Queue to hold incoming messages
msg_queue = Queue()

lock = threading.Lock()
callbacks_done = threading.Condition(lock)

receiver_active = False
timer_started = False
loop_start_time = None
active_workers = 0

all_loop_results = []


# ===== Background Image Worker =====
def image_worker():
    global active_workers

    while True:
        topic, image_b64, filename_hint = msg_queue.get()

        with lock:
            active_workers += 1

        try:
            with lock:
                if not receiver_active:
                    continue

            image_data = base64.b64decode(image_b64)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                print("❌ Could not decode image.")
                continue

            with lock:
                if not receiver_active:
                    continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            topic_id = topic.split("/")[-1]
            out_filename = f"{topic_id}_{timestamp}.jpg"
            save_path = os.path.join(output_base, out_filename)

            cv2.imwrite(save_path, image)

        except Exception as e:
            print(f"❌ Error processing image: {e}")

        finally:
            with lock:
                active_workers -= 1
                if active_workers == 0:
                    callbacks_done.notify_all()

            msg_queue.task_done()


def wait_for_workers_to_finish():
    msg_queue.join()

    with lock:
        while active_workers > 0:
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


# ===== HTTP Handler =====
class ImageUploadHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def log_message(self, format, *args):
        # Disable default HTTP request logs
        return

    def do_POST(self):
        global timer_started, loop_start_time

        if self.path != "/upload":
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(b'{"error": "Invalid JSON"}')
            return

        topic = data.get("topic", "images/unknown")
        filename = data.get("filename", "unknown.jpg")
        image_b64 = data.get("image_b64")

        if image_b64 is None:
            self._set_headers(400)
            self.wfile.write(b'{"error": "Missing image_b64"}')
            return

        with lock:
            if not receiver_active:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ignored"}')
                return

            if not timer_started:
                timer_started = True
                loop_start_time = time.time()
                print(f"🟢 First image received. {RUN_AFTER_FIRST_IMAGE}-second counter started.")

        msg_queue.put((topic, image_b64, filename))

        self._set_headers(200)
        self.wfile.write(b'{"status": "ok"}')


def run_http_server():
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, ImageUploadHandler)

    print(f"🚀 HTTP image receiver running on {HOST}:{PORT}")
    print("📨 POST images as JSON to /upload")

    httpd.serve_forever()


def main():
    global receiver_active, timer_started, loop_start_time

    print("🚀 Starting HTTP benchmark receiver")
    print(f"🌐 Listening on: {HOST}:{PORT}")
    print("📨 Expected JSON keys: topic, filename, image_b64")

    threading.Thread(target=image_worker, daemon=True).start()
    threading.Thread(target=run_http_server, daemon=True).start()

    time.sleep(1)

    try:
        for loop_number in range(1, NUMBER_OF_LOOPS + 1):
            print("\n==============================")
            print(f"🚀 Starting HTTP loop {loop_number}/{NUMBER_OF_LOOPS}")
            print("==============================")

            with lock:
                receiver_active = True
                timer_started = False
                loop_start_time = None

            wait_start = time.time()

            while True:
                with lock:
                    started = timer_started
                    start_time_copy = loop_start_time

                if started:
                    elapsed = time.time() - start_time_copy
                    if elapsed >= RUN_AFTER_FIRST_IMAGE:
                        break
                else:
                    if time.time() - wait_start > FIRST_IMAGE_TIMEOUT:
                        print(f"⚠️ No image received within {FIRST_IMAGE_TIMEOUT} seconds.")
                        break

                time.sleep(0.01)

            if timer_started:
                print(
                    f"\n⏱️ {RUN_AFTER_FIRST_IMAGE} seconds completed after first image. "
                    "Stopping loop..."
                )

            with lock:
                receiver_active = False

            wait_for_workers_to_finish()

            total_images, total_size_mb, images_per_sec, mb_per_sec = folder_stats_and_delete(
                output_base
            )

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
        write_csv_results(all_loop_results)
        print("🎉 HTTP receiver script terminated.")


if __name__ == "__main__":
    main()
