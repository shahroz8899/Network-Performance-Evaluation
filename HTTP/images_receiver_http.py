import os
import cv2
import base64
import numpy as np
from datetime import datetime
from queue import Queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# Folder setup (same as MQTT version)
output_base = './analyzed_images'
os.makedirs(output_base, exist_ok=True)

# Thread-safe queue to hold messages (topic, image_b64)
msg_queue = Queue()


# ===== Background worker =====
def image_worker():
    while True:
        topic, image_b64 = msg_queue.get()

        try:
            image_data = base64.b64decode(image_b64)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                print("❌ Could not decode image.")
                continue

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            topic_id = topic.split("/")[-1]
            filename = f"{topic_id}_{timestamp}.jpg"
            save_path = os.path.join(output_base, filename)

            cv2.imwrite(save_path, image)
            print(f"✅ Image saved: {save_path}")

        except Exception as e:
            print(f"❌ Error processing image: {e}")


# Start the background image worker thread
threading.Thread(target=image_worker, daemon=True).start()


# ===== HTTP handler =====
class ImageUploadHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self):
        if self.path != "/upload":
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(b'{"error": "Invalid JSON"}')
            return

        topic = data.get("topic", "images/unknown")
        image_b64 = data.get("image_b64")

        if image_b64 is None:
            self._set_headers(400)
            self.wfile.write(b'{"error": "Missing image_b64"}')
            return

        # Optional: filename is not strictly needed, but we accept it
        filename = data.get("filename", "unknown.jpg")
        # You could log this filename if you want
        # print(f"Received image for topic={topic}, filename={filename}")

        # Queue for background processing
        msg_queue.put((topic, image_b64))

        self._set_headers(200)
        self.wfile.write(b'{"status": "ok"}')


def run_server(host="0.0.0.0", port=8000):
    server_address = (host, port)
    httpd = HTTPServer(server_address, ImageUploadHandler)
    print(f"🚀 HTTP image receiver running on {host}:{port}")
    print("    POST images as JSON to /upload")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()