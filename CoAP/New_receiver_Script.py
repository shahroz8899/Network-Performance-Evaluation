import asyncio
import os
import csv
import time
from datetime import datetime

import aiocoap
import aiocoap.resource as resource


HOST = "0.0.0.0"
PORT = 5683

PATH_SEGMENTS = ["office", "pi1", "image"]
REPLICAS = 1

output_base = "./analyzed_images_coap"
os.makedirs(output_base, exist_ok=True)

RUN_AFTER_FIRST_IMAGE = 10
NUMBER_OF_LOOPS = 50
FIRST_IMAGE_TIMEOUT = 60

csv_file = "coap_receiver_results.csv"

receiver_active = False
timer_started = False
loop_start_time = None
all_loop_results = []

lock = asyncio.Lock()


def build_paths(path_segments, replicas):
    if replicas <= 0:
        return []

    paths = [path_segments]

    for i in range(1, replicas):
        replica_path = list(path_segments)
        replica_path[-1] = f"{replica_path[-1]}_{i}"
        paths.append(replica_path)

    return paths


def folder_stats_and_delete(folder):
    image_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    total_images = len(image_files)
    total_size_bytes = sum(os.path.getsize(f) for f in image_files)
    total_size_mb = total_size_bytes / 1024 / 1024

    images_per_sec = total_images / RUN_AFTER_FIRST_IMAGE
    mb_per_sec = total_size_mb / RUN_AFTER_FIRST_IMAGE

    print("\n📊 Loop Results")
    print(f"Total images: {total_images}")
    print(f"Total size: {total_size_mb:.1f} MB")
    print(f"Images/sec: {images_per_sec:.2f}")
    print(f"MB/sec: {mb_per_sec:.2f}")

    for f in image_files:
        os.remove(f)

    print("🗑️ Images deleted.")

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

    print(f"💾 CSV saved: {csv_file}")


class ImageUploadResource(resource.Resource):

    async def render_put(self, request):
        global receiver_active, timer_started, loop_start_time

        img_bytes = bytes(request.payload)

        async with lock:
            if not receiver_active:
                return aiocoap.Message(code=aiocoap.CHANGED, payload=b"IGNORED")

            if not timer_started:
                timer_started = True
                loop_start_time = time.time()
                print(f"🟢 First image received. {RUN_AFTER_FIRST_IMAGE}-second timer started.")

        filename = os.path.join(output_base, f"coap_image_{time.time_ns()}.jpg")

        try:
            with open(filename, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"❌ Failed to save image: {e}")
            return aiocoap.Message(code=aiocoap.INTERNAL_SERVER_ERROR)

        return aiocoap.Message(code=aiocoap.CHANGED, payload=b"OK")


async def benchmark_loop():
    global receiver_active, timer_started, loop_start_time

    for loop_number in range(1, NUMBER_OF_LOOPS + 1):
        print("\n==============================")
        print(f"🚀 Starting CoAP loop {loop_number}/{NUMBER_OF_LOOPS}")
        print("==============================")

        async with lock:
            receiver_active = True
            timer_started = False
            loop_start_time = None

        wait_start = time.time()

        while True:
            async with lock:
                started = timer_started
                start_time_copy = loop_start_time

            if started:
                if time.time() - start_time_copy >= RUN_AFTER_FIRST_IMAGE:
                    break
            else:
                if time.time() - wait_start > FIRST_IMAGE_TIMEOUT:
                    print(f"⚠️ No image received within {FIRST_IMAGE_TIMEOUT} seconds.")
                    break

            await asyncio.sleep(0.01)

        if timer_started:
            print(f"\n⏱️ {RUN_AFTER_FIRST_IMAGE} seconds completed. Stopping loop...")

        async with lock:
            receiver_active = False

        await asyncio.sleep(0.5)

        total_images, total_size_mb, images_per_sec, mb_per_sec = folder_stats_and_delete(output_base)

        result = {
            "loop_number": loop_number,
            "run_duration_seconds": RUN_AFTER_FIRST_IMAGE,
            "total_images": total_images,
            "total_size_mb": total_size_mb,
            "images_per_sec": images_per_sec,
            "mb_per_sec": mb_per_sec,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success" if total_images > 0 else "no_images_received"
        }

        all_loop_results.append(result)
        write_csv_results(all_loop_results)

        print(f"✅ Loop {loop_number}/{NUMBER_OF_LOOPS} completed.")
        await asyncio.sleep(1)


async def main():
    root = resource.Site()
    image_resource = ImageUploadResource()

    for path in build_paths(PATH_SEGMENTS, REPLICAS):
        root.add_resource(path, image_resource)
        print(f"📡 Registered path: /{'/'.join(path)}")

    await aiocoap.Context.create_server_context(root, bind=(HOST, PORT))

    print(f"🚀 CoAP receiver listening on coap://{HOST}:{PORT}")
    print("📨 Expected payload: raw JPEG bytes")

    try:
        await benchmark_loop()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
    finally:
        write_csv_results(all_loop_results)
        print("🎉 CoAP receiver terminated.")


if __name__ == "__main__":
    asyncio.run(main())
