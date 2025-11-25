import asyncio
import logging
import os
import time

import cv2
import aiocoap

# ===== Configuration =====
# CoAP server (worker) IP and port
SERVER_IP = "192.168.1.176"   
SERVER_PORT = 5683            # default CoAP port


PATH_SEGMENTS = ["office", "pi1", "image"]

# Total "replicas" per image (for similarity with Zenoh; typically 1)
REPLICAS = 1

# Publish the same encoded image this many times (like MQTT/ZENOH MULTIPLY_FACTOR)
MULTIPLY_FACTOR = 12

# Run script for a custom duration (in seconds)
RUN_DURATION = 10  # <-- Change this (e.g., 30, 120, 300 seconds, etc.)


# Save to disk only at the end (optional)
SAVE_TO_DISK = False
PROCESSED_FOLDER = "sent_images"

IMAGE_COUNTER_FILE = "image_counter.txt"

# ===== Logging =====
logging.basicConfig(
    filename="image_capture_coap.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s"
)

# ===== Counter utilities =====
def get_next_image_number(counter_file: str) -> int:
    try:
        with open(counter_file, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return 1


def update_image_number(counter_file: str, number: int):
    with open(counter_file, "w") as file:
        file.write(str(number))


def build_uris(server_ip: str, server_port: int, path_segments, replicas: int):
   
    if replicas <= 0:
        return []

    base_path = "/".join(path_segments)
    uris = [f"coap://{server_ip}:{server_port}/{base_path}"]

    if replicas > 1:
        for i in range(1, replicas):
            segments = list(path_segments)
            segments[-1] = f"{segments[-1]}_{i}"
            path = "/".join(segments)
            uris.append(f"coap://{server_ip}:{server_port}/{path}")

    return uris

async def coap_publisher():
    print(f"[CoAP] Connecting to server @ coap://{SERVER_IP}:{SERVER_PORT}/ ...")

    # Create CoAP client context
    context = await aiocoap.Context.create_client_context()

    # Build URIs (analogous to Zenoh keys)
    uris = build_uris(SERVER_IP, SERVER_PORT, PATH_SEGMENTS, REPLICAS)
    for uri in uris:
        print(f"[CoAP] Will PUT images to: {uri}")

    # Ensure local save folder exists (for SAVE_TO_DISK)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    # ===== Camera Init =====
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.01)

    if not cap.isOpened():
        print("[ERROR] Camera could not be opened")
        return

    # ===== Timing Setup =====
    start_time = time.time()

    try:
        running = True
        while running:
            elapsed = time.time() - start_time
            if elapsed > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                break

            loop_start = time.time()

            # Get next image number (for local saving)
            image_number = get_next_image_number(IMAGE_COUNTER_FILE)
            filename = f"image_{image_number:04d}.jpg"

            # --- Capture ---
            t1 = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Frame capture failed")
                continue
            t2 = time.time()

            # Check time again after capture
            if time.time() - start_time > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached during capture. Stopping.")
                break

            # --- JPEG Encode ---
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                print("[ERROR] JPEG encoding failed")
                continue
            jpeg_bytes = buf.tobytes()
            t3 = time.time()

            # Check time again after encode
            if time.time() - start_time > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached during encode. Stopping.")
                break

            # --- PUT raw bytes to all URIs, MULTIPLY_FACTOR times ---
            total_requests = 0
            for uri in uris:
                for _ in range(MULTIPLY_FACTOR):
                    # Check before each PUT
                    if time.time() - start_time > RUN_DURATION:
                        print(f"Run duration of {RUN_DURATION} seconds reached during PUTs. Stopping.")
                        running = False
                        break

                    request = aiocoap.Message(
                        code=aiocoap.PUT,
                        uri=uri,
                        payload=jpeg_bytes,
                    )
                    try:
                        # Optionally add timeout to avoid hanging PUT forever
                        # response = await asyncio.wait_for(context.request(request).response, timeout=1.0)
                        response = await context.request(request).response
                    except Exception as e:
                        print(f"[CoAP] PUT failed for {uri}: {e}")
                    total_requests += 1

                if not running:
                    break

            t4 = time.time()

            if not running:
                break

            # --- Optionally save one copy locally on the camera node ---
            if SAVE_TO_DISK:
                try:
                    out_path = os.path.join(PROCESSED_FOLDER, filename)
                    with open(out_path, "wb") as f:
                        f.write(jpeg_bytes)
                except Exception as e:
                    print(f"[ERROR] Failed to save image locally: {e}")

            # Update image counter
            update_image_number(IMAGE_COUNTER_FILE, image_number + 1)

            # Print timing
            print(
                f"CoAP PUTs: {total_requests} | "
                f"Capture: {t2 - t1:.4f}s | Encode: {t3 - t2:.4f}s | "
                f"PUTs: {t4 - t3:.4f}s | Total loop: {t4 - loop_start:.4f}s"
            )

            await asyncio.sleep(0.001)


    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        cap.release()
        print("Camera released.")
        # context will be closed when program exits


def main():
    asyncio.run(coap_publisher())


if __name__ == "__main__":
    main()