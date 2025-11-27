import asyncio
import os
import time

import aiocoap
import aiocoap.resource as resource

SAVE_DIR = "received_images"
os.makedirs(SAVE_DIR, exist_ok=True)


class ImageUploadResource(resource.Resource):


    def __init__(self, save_dir: str):
        super().__init__()
        self.save_dir = save_dir
        self.count = 0
        self.start = time.time()

    async def render_put(self, request: aiocoap.Message) -> aiocoap.Message:
        # request.payload is the raw JPEG bytes
        img_bytes = bytes(request.payload)

        # Save with timestamp-based filename (like Zenoh subscriber)
        ts_ns = time.time_ns()
        filename = os.path.join(self.save_dir, f"img_{ts_ns}.jpg")
        try:
            with open(filename, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"[ERROR] Failed to save image: {e}")
            # Respond with 5.00 Internal Server Error
            return aiocoap.Message(code=aiocoap.INTERNAL_SERVER_ERROR)

        # Throughput counting
        self.count += 1
        now = time.time()
        elapsed = now - self.start
        if elapsed >= 1.0:
            print(
                f"Received {self.count} images in {elapsed:.2f}s "
                f"-> {self.count / elapsed:.1f} img/s"
            )
            self.count = 0
            self.start = now

        # Respond with CHANGED (2.04)
        return aiocoap.Message(code=aiocoap.CHANGED, payload=b"OK")


async def main():
    # Resource tree
    root = resource.Site()

    # Path segments = /office/pi1/image
    image_resource = ImageUploadResource(SAVE_DIR)
    root.add_resource(["office", "pi1", "image"], image_resource)

    # Bind on default CoAP port 5683, all interfaces
    # (you can change bind address/port if needed)
    await aiocoap.Context.create_server_context(root, bind=("0.0.0.0", 5683))

    print("[CoAP] Image server listening on coap://0.0.0.0:5683/office/pi1/image")

    # Run forever
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())