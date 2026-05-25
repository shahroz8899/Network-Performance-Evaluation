

````markdown
# HTTP Image Transmission Benchmark

This project is used to test image transmission between Raspberry Pi sender devices and receiver machines using HTTP.

The sender captures images from a camera, converts each image into Base64 format, and sends it as a JSON HTTP POST request to one or more receiver machines.

The receiver accepts incoming images, saves them temporarily, measures the received data rate, writes the results to a CSV file, and deletes the images after each test loop.

This setup is useful for testing:

- One sender to one receiver
- One sender to multiple receivers
- Multiple senders to one receiver
- Multiple independent sender-receiver pipelines

The receiver measures:

- Total received images
- Total received data in MB
- Images per second
- MB per second
- Stability across 50 repeated loops

---

## 2. How it works

The system uses direct HTTP communication.

```text
Sender Pi  --->  HTTP POST  --->  Receiver
````

There is no broker in HTTP.

This means the sender must know the receiver address directly.

Example receiver URL:

```python
"http://###.###.###.###:8000/upload"
```

The sender sends JSON data like this:

```json
{
  "topic": "images/pi1",
  "filename": "image_0001.jpg",
  "image_b64": "base64_encoded_image_data"
}
```

The receiver listens on:

```text
0.0.0.0:8000
```

and accepts requests at:

```text
/upload
```

---

## 3. Folder structure

Recommended structure:

```text
HTTP/
├── sender.py
├── receiver.py
├── requirements.txt
├── image_counter.txt
├── image_capture_http.log
├── analyzed_images_http/
└── http_receiver_results.csv
```

---

## 4. Create a Python virtual environment

Run this on every sender and receiver machine.

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

After activation, the terminal should show:

```bash
(venv)
```

Upgrade pip:

```bash
python3 -m pip install --upgrade pip
```

---

## 5. Install requirements

Install the required packages:

```bash
pip install opencv-python numpy requests
```

The receiver needs:

```bash
pip install opencv-python numpy
```

The sender needs:

```bash
pip install opencv-python requests
```

A simple `requirements.txt` can be:

```text
opencv-python
numpy
requests
```

Install using:

```bash
pip install -r requirements.txt
```

---

## 6. Receiver script configuration

In `receiver.py`, check these settings:

```python
HOST = "0.0.0.0"
PORT = 8000
```

The receiver will listen on all network interfaces.

The benchmark settings are:

```python
RUN_AFTER_FIRST_IMAGE = 10
NUMBER_OF_LOOPS = 50
FIRST_IMAGE_TIMEOUT = 60
```

Meaning:

* Each loop starts when the first image arrives
* Each loop runs for 10 seconds
* The test repeats 50 times
* If no image arrives within 60 seconds, the loop is marked as no image received

The receiver saves results in:

```text
http_receiver_results.csv
```

---

## 7. Sender script configuration

In `sender.py`, the important part is:

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]
```

Replace:

```text
###.###.###.###
```

with the receiver IP address.

Common sender settings:

```python
TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
RUN_DURATION = 700
```

Explanation:

| Setting           | Meaning                                 |
| ----------------- | --------------------------------------- |
| `HTTP_SERVERS`    | List of receivers                       |
| `TOPIC_BASE`      | Topic name included in the JSON payload |
| `REPLICAS`        | Creates extra topic names if needed     |
| `MULTIPLY_FACTOR` | Sends the same image multiple times     |
| `RUN_DURATION`    | How long the sender runs                |

For normal experiments, use:

```python
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

---

## 8. How to run

### Step 1: Start receiver

On each receiver machine:

```bash
source venv/bin/activate
python3 receiver.py
```

Expected output:

```text
HTTP image receiver running on 0.0.0.0:8000
POST images as JSON to /upload
```

### Step 2: Start sender

On each sender Pi:

```bash
source venv/bin/activate
python3 sender.py
```

---

# 9. Test cases

## Case 1: One Sender to One Receiver

### Architecture

```text
Pi 1  --->  Receiver 1
```

### Sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Collect http_receiver_results.csv from Receiver 1
```

---

## Case 2: One Sender to Two Receivers

### Architecture

```text
          ---> Receiver 1
Pi 1
          ---> Receiver 2
```

### Sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Receiver configuration

Run the same `receiver.py` on both receiver machines.

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start receiver.py on Receiver 2
3. Start sender.py on Pi 1
4. Collect one CSV file from each receiver
```

---

## Case 3: One Sender to Three Receivers

### Architecture

```text
          ---> Receiver 1
Pi 1      ---> Receiver 2
          ---> Receiver 3
```

### Sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
    "http://###.###.###.###:8000/upload",
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Run order

```text
1. Start receiver.py on all three receivers
2. Start sender.py on Pi 1
3. Collect CSV files from all receivers
```

---

## Case 4: Two Senders to One Receiver

### Architecture

```text
Pi 1  --->
          Receiver 1
Pi 2  --->
```

### Pi 1 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Pi 2 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

Both senders use the same receiver URL.

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Start sender.py on Pi 2
4. Collect CSV file from Receiver 1
```

The receiver measures the combined traffic from both Pis.

---

## Case 5: Two Senders to Two Receivers

### Architecture

```text
Pi 1  --->  Receiver 1

Pi 2  --->  Receiver 2
```

This uses two independent HTTP pipelines.

### Pi 1 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Pi 2 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

Each Pi uses a different receiver IP.

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start receiver.py on Receiver 2
3. Start sender.py on Pi 1
4. Start sender.py on Pi 2
5. Collect one CSV file from each receiver
```

---

## Case 6: Three Senders to One Receiver

### Architecture

```text
Pi 1  --->
Pi 2  --->  Receiver 1
Pi 3  --->
```

### All sender configurations

Each Pi uses the same receiver URL:

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]

TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Start sender.py on Pi 2
4. Start sender.py on Pi 3
5. Collect CSV file from Receiver 1
```

The receiver measures the total received traffic from all three senders.

---

## Case 7: Three Senders to Three Receivers

### Architecture

```text
Pi 1  --->  Receiver 1

Pi 2  --->  Receiver 2

Pi 3  --->  Receiver 3
```

This uses three independent HTTP pipelines.

### Pi 1 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]
```

### Pi 2 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]
```

### Pi 3 sender configuration

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]
```

Each Pi points to its own receiver.

Use the same general settings:

```python
TOPIC_BASE = "images/pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start receiver.py on Receiver 2
3. Start receiver.py on Receiver 3
4. Start sender.py on Pi 1
5. Start sender.py on Pi 2
6. Start sender.py on Pi 3
7. Collect CSV files from all receivers
```

---

# 10. Output files

Each receiver creates:

```text
http_receiver_results.csv
```

This file contains:

```text
loop_number
run_duration_seconds
total_images
total_size_mb
images_per_second
mb_per_second
timestamp
status
```

At the bottom of the CSV file, average values are also written.

Recommended naming after each test:

```text
Case_1_One_to_One_http_receiver_results.csv
Case_2_One_to_Two_receiver_1.csv
Case_2_One_to_Two_receiver_2.csv
Case_3_One_to_Three_receiver_1.csv
Case_3_One_to_Three_receiver_2.csv
Case_3_One_to_Three_receiver_3.csv
```

---

# 11. Notes

* Start receivers before senders.
* Make sure the receiver port is open.
* Default port is `8000`.
* HTTP does not use a broker.
* Sender must contain the receiver URL.
* For one-to-many tests, add multiple receiver URLs in `HTTP_SERVERS`.
* For many-to-one tests, all senders use the same receiver URL.
* For independent pipelines, each sender points to its own receiver.

---

# 12. Troubleshooting

## Receiver not getting images

Check that the receiver is running:

```bash
python3 receiver.py
```

Check that the sender has the correct receiver IP:

```python
HTTP_SERVERS = [
    "http://###.###.###.###:8000/upload",
]
```

Test the port:

```bash
nc -vz ###.###.###.### 8000
```

## Port already in use

If port `8000` is already used, change the receiver port:

```python
PORT = 8001
```

Then update the sender URL:

```python
"http://###.###.###.###:8001/upload"
```


---

# 13. Experiment checklist

Before each test:

```text
1. Confirm correct HTTP_SERVERS in sender.py
2. Confirm receiver.py is running on each required receiver
3. Confirm port 8000 is reachable
4. Run sender.py on required Pis
5. Wait until receiver completes 50 loops
6. Rename and save CSV result files
7. Clear old logs/images if needed
```



