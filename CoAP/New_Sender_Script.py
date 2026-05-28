import asyncio
import logging
import os
import time

import cv2
import aiocoap


COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    },
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    },
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    },
]

REPLICAS = 1
MULTIPLY_FACTOR = 10
RUN_DURATION = 10000

SAVE_TO_DISK = False
PROCESSED_FOLDER = "sent_images"
IMAGE_COUNTER_FILE = "image_counter.txt"

logging.basicConfig(
    filename="image_capture_coap.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s"
)


def get_next_image_number(counter_file):
    try:
        with open(counter_file, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return 1


def update_image_number(counter_file, number):
    with open(counter_file, "w") as file:
        file.write(str(number))


def build_uris(server, replicas):
    ip = server["ip"]
    port = server["port"]
    path_segments = server["path_segments"]

    if replicas <= 0:
        return []

    base_path = "/".join(path_segments)
    uris = [f"coap://{ip}:{port}/{base_path}"]

    for i in range(1, replicas):
        replica_segments = list(path_segments)
        replica_segments[-1] = f"{replica_segments[-1]}_{i}"
        replica_path = "/".join(replica_segments)
        uris.append(f"coap://{ip}:{port}/{replica_path}")

    return uris


async def coap_publisher():
    print("[CoAP] Starting sender")

    context = await aiocoap.Context.create_client_context()

    all_uris = []

    for server in COAP_SERVERS:
        uris = build_uris(server, REPLICAS)
        all_uris.extend(uris)

    print("[CoAP] Sending to:")
    for uri in all_uris:
        print(f"  {uri}")

    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    time.sleep(0.1)

    if not cap.isOpened():
        print("❌ Camera could not be opened.")
        return

    start_time = time.time()

    try:
        while True:
            if time.time() - start_time > RUN_DURATION:
                print(f"Run duration of {RUN_DURATION} seconds reached. Stopping.")
                break

            loop_start = time.time()

            image_number = get_next_image_number(IMAGE_COUNTER_FILE)
            filename = f"image_{image_number:04d}.jpg"

            ret, frame = cap.read()

            if not ret:
                print("❌ Frame capture failed.")
                time.sleep(0.1)
                continue

            ok, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 95]
            )

            if not ok:
                print("❌ JPEG encoding failed.")
                continue

            jpeg_bytes = buf.tobytes()

            total_requests = 0

            for uri in all_uris:
                for i in range(MULTIPLY_FACTOR):
                    if time.time() - start_time > RUN_DURATION:
                        break

                    request = aiocoap.Message(
                        code=aiocoap.PUT,
                        uri=uri,
                        payload=jpeg_bytes
                    )

                    try:
                        await asyncio.wait_for(
                            context.request(request).response,
                            timeout=5.0
                        )
                        total_requests += 1

                        logging.info(
                            f"CoAP PUT {i + 1}/{MULTIPLY_FACTOR} "
                            f"of {filename} to {uri}"
                        )

                    except Exception as e:
                        logging.error(f"CoAP PUT failed to {uri}: {e}")
                        print(f"⚠️ CoAP PUT failed to {uri}: {e}")

            if SAVE_TO_DISK:
                try:
                    out_path = os.path.join(PROCESSED_FOLDER, filename)
                    with open(out_path, "wb") as f:
                        f.write(jpeg_bytes)
                except Exception as e:
                    logging.error(f"Failed to save local image: {e}")

            update_image_number(IMAGE_COUNTER_FILE, image_number + 1)

            print(
                f"CoAP PUTs: {total_requests} | "
                f"Total loop: {time.time() - loop_start:.4f}s"
            )

            await asyncio.sleep(0.001)

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        cap.release()
        print("Camera released.")


def main():
    asyncio.run(coap_publisher())


if __name__ == "__main__":
    main()
