import time
import zenoh
import os

KEY_EXPR = "office/pi1/image"
SAVE_DIR = "received_images"

def main():
    os.makedirs(SAVE_DIR, exist_ok=True)

        # Configure Zenoh as a peer listening on TCP 0.0.0.0:7447
    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    conf.insert_json5("listen/endpoints", '["tcp/0.0.0.0:7447"]')

    session = zenoh.open(conf)
    print("[Zenoh] Worker listening on tcp/0.0.0.0:7447")


    count = 0
    start = time.time()

    def listener(sample):
        nonlocal count, start
        count += 1

        # ---- Save RAW JPEG image ----
        try:
            img_bytes = bytes(sample.payload)
            ts = time.time_ns()
            filename = os.path.join(SAVE_DIR, f"img_{ts}.jpg")
            with open(filename, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            print("Error saving image:", e)

        # ---- Throughput counter ----
        now = time.time()
        elapsed = now - start
        if elapsed >= 1.0:
            print(f"Received {count} images in {elapsed:.2f}s -> {count/elapsed:.1f} img/s")
            count = 0
            start = now

    sub = session.declare_subscriber(KEY_EXPR, listener)

    print(f"[Zenoh] Subscriber running on key: {KEY_EXPR}")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Closing subscriber...")
    finally:
        sub.undeclare()
        session.close()

if __name__ == "__main__":
    main()
