#  High-Throughput HTTP Image Streaming with Raspberry Pis**

## **📌 Project Overview**

This project investigates the **performance limitations of an HTTP-based high-throughput image transmission pipeline**, where multiple **Raspberry Pis act as publishers**, capturing camera frames and sending them via HTTP to one or more **worker nodes (subscribers)** on a local network.

The goal is to measure **what becomes the bottleneck** when streaming large volumes of images:

### **1️⃣ The Network Medium?**

* 5 GHz Wi-Fi
* Ethernet LAN


### **2️⃣ The HTTP Middleware Stack?**

* One sender → one worker
* Multiple senders → one shared worker
* Pairs of senders and receivers (independent pipelines)
* Parallel vs competing HTTP pipelines

Each Raspberry Pi captures **480p JPEG images (~60–70 KB)** and sends them through HTTP at high rates, controlled by a scaling parameter (`MULTIPLY_FACTOR`).
Worker nodes measure the **actual throughput (images/second)** received under each scenario.

---

# **📂 Project Structure**

```
.
│
├── image_capture_http.py      # Raspberry Pi side (sender)
├── images_receiver_http.py    # Worker node (receiver)
├── image_counter.txt          # Persistent counter for filenames
└── analyzed_images/           # Saved images (auto-created)
```

---

# **📘 Script Documentation**

---

## **1) images_receiver_http.py — Worker/Subscriber**

This script receives images over HTTP, decodes them, and saves them to disk.

### **Main Responsibilities**

✔ Start an HTTP server (`/upload` endpoint)
✔ Accept JSON POST requests containing:

* `topic`
* `filename`
* `image_b64` (base64 JPEG)
  ✔ Queue each incoming frame
  ✔ A background worker thread decodes & saves images
  ✔ Stores files in `./analyzed_images/` with timestamped names

### **Why it uses a queue**

The HTTP layer stays lightweight and fast.
Heavy CPU tasks (JPEG decoding, file I/O) run in a background thread.

This prevents slowdowns and keeps measured ingestion rate accurate.

---

## **2) image_capture_http.py — Raspberry Pi Publisher**

This script captures camera frames, encodes them, and sends them repeatedly via HTTP.

### **Main Steps**

1. Capture image from Pi camera (`cv2.VideoCapture`)
2. Encode to JPEG with quality=95
3. Convert JPEG → Base64
4. Send the same image **multiple times**
5. Repeat for the duration of the run

### **Transmission Scaling with `MULTIPLY_FACTOR`**

```
Total HTTP POSTs per frame = REPLICAS × MULTIPLY_FACTOR
```

* `REPLICAS`: Number of different topics
* `MULTIPLY_FACTOR`: How many repeated sends per topic
* Increasing `MULTIPLY_FACTOR` increases:

  * Requests/sec
  * Network load
  * Worker pressure
  * Throughput measurement resolution

Example with default settings:

```
REPLICAS = 1
MULTIPLY_FACTOR = 20
→ 20 image POSTs per captured frame
```

If you increase:

```
MULTIPLY_FACTOR = 200
→ 200 POSTs per frame (10× traffic)
```

This lets you artificially stress-test the network **without increasing camera FPS**.

---

# **🛠️ Setup Instructions**

---

## **1️⃣ Create a Python Virtual Environment**

On all machines (Pis + workers):

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```cmd
venv\Scripts\activate
```

---

## **2️⃣ Install Dependencies**

```bash
pip install opencv-python requests numpy
```

The receiver also needs:

```bash
pip install pillow
```

---

# **🚀 Running the Scripts**

---

## **Start the Receiver (Worker Node)**

On the worker machine:

```bash
python3 images_receiver_http.py
```

It will start listening on:

```
http://0.0.0.0:8000/upload
```

You can change the port in:

```python
run_server(host="0.0.0.0", port=8000)
```

---

## **Start the Sender (Raspberry Pi)**

Edit this line in `image_capture_http.py`:

```python
HTTP_SERVER = "http://<WORKER_IP>:8000/upload"
```

Then run:

```bash
python3 image_capture_http.py
```

---

# **📡 Experimental Scenarios**

Below are the experiment configurations and how to run them.

---

# **🟦 Case 1 — 1 Pi → 1 Worker (Single HTTP Pipeline)**

### Setup

One Pi sends images to **one worker**.

### Steps

Receiver (Worker):

```bash
python3 images_receiver_http.py   # on Worker1 (IP: 192.168.1.100)
```

Sender (Pi):

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

Run:

```bash
python3 image_capture_http.py
```

---

# **🟩 Case 2 — 2 Pis → 1 Worker (Shared HTTP Pipeline)**

Both Pis send to the **same worker IP + port**.

### Receiver:

```bash
python3 images_receiver_http.py   # Worker IP: 192.168.1.100
```

### Sender (Pi #1):

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

### Sender (Pi #2):

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

Both Pis run simultaneously.

---

# **🟧 Case 3 — 3 Pis → 1 Worker (Heavy Shared HTTP Load)**

Same as Case 2, but 3 Pis.

All senders target the same worker:

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

This tests how well the worker’s single HTTP pipeline scales under contention.

---

# **🟪 Case 4 — 2 Pis → 2 Workers (Independent HTTP Pipelines)**

This tests whether the bottleneck is the shared worker or HTTP overhead.

### Workers:

* Worker1 → `192.168.1.100`
* Worker2 → `192.168.1.101`

### Sender (Pi #1):

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

### Sender (Pi #2):

```
HTTP_SERVER = "http://192.168.1.101:8000/upload"
```

Two independent pipelines → no contention.

---

# **🟥 Case 5 — 3 Pis → 3 Workers (Fully Parallel Pipelines)**

Best-case scenario for high throughput.

### Workers:

* Worker1 → `192.168.1.100`
* Worker2 → `192.168.1.101`
* Worker3 → `192.168.1.102`

### Senders:

Pi #1:

```
HTTP_SERVER = "http://192.168.1.100:8000/upload"
```

Pi #2:

```
HTTP_SERVER = "http://192.168.1.101:8000/upload"
```

Pi #3:

```
HTTP_SERVER = "http://192.168.1.102:8000/upload"
```

Each Pi has its **own dedicated worker**.

---

# **📊 Throughput Measurement**

Worker nodes measure throughput based on:

* Number of images saved per second
* Per-topic arrival distribution
* Timestamp encoded in filenames

You can compute throughput by counting files:

```bash
ls analyzed_images | wc -l
```

Or using a Python script for finer timestamp analysis.

---

# **⚙️ How to Scale Load (Increasing MULTIPLY_FACTOR)**

Edit in `image_capture_http.py`:

```python
MULTIPLY_FACTOR = 20
```



