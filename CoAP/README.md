Below is a complete `README.md` for your **CoAP image transmission benchmark**.

````markdown
# CoAP Image Transmission Benchmark

## Overview

This project tests image transmission performance using CoAP between Raspberry Pi sender devices and receiver machines.

The sender captures camera images, encodes them as JPEG bytes, and sends them to one or more CoAP receivers using PUT requests.

The receiver accepts incoming images, saves them temporarily, measures throughput, writes results into a CSV file, and deletes images after each test loop.

This experiment measures:

- Total images received
- Total data received in MB
- Images per second
- MB per second
- Stability across 50 repeated loops

---

## How CoAP works in this experiment

CoAP uses a client-server model.

```text
Sender Pi  --->  CoAP PUT  --->  Receiver
````

The sender sends raw JPEG bytes to a CoAP URI such as:

```text
coap://###.###.###.###:5683/office/pi1/image
```

The receiver listens on:

```text
0.0.0.0:5683
```

and receives images at:

```text
/office/pi1/image
```

There is no broker in CoAP.
The sender must know the receiver IP address and port directly.

---

## Project files

```text
CoAP/
├── sender.py
├── receiver.py
├── image_counter.txt
├── image_capture_coap.log
├── analyzed_images_coap/
└── coap_receiver_results.csv
```

---

## Create virtual environment

Run this on every sender and receiver machine.

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Upgrade pip:

```bash
python3 -m pip install --upgrade pip
```

---

## Install requirements

Install these packages:

```bash
pip install aiocoap opencv-python numpy
```

If only running receiver:

```bash
pip install aiocoap numpy
```

If running sender:

```bash
pip install aiocoap opencv-python numpy
```

Optional `requirements.txt`:

```text
aiocoap
opencv-python
numpy
```

Install using:

```bash
pip install -r requirements.txt
```

---

## Receiver configuration

Main receiver settings:

```python
HOST = "0.0.0.0"
PORT = 5683

PATH_SEGMENTS = ["office", "pi1", "image"]
REPLICAS = 1
```

Benchmark settings:

```python
RUN_AFTER_FIRST_IMAGE = 10
NUMBER_OF_LOOPS = 50
FIRST_IMAGE_TIMEOUT = 60
```

Meaning:

* Receiver waits for the first image
* After first image arrives, it records for 10 seconds
* It repeats this 50 times
* After each loop, it calculates results and deletes saved images

Receiver output:

```text
coap_receiver_results.csv
```

---

## Sender configuration

Main sender settings:

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]

REPLICAS = 1
MULTIPLY_FACTOR = 1
RUN_DURATION = 10000
```

For normal experiments, use:

```python
MULTIPLY_FACTOR = 1
```

Using a high value such as `10` can overload CoAP because image payloads are large.

---

## Run receiver

On receiver machine:

```bash
source venv/bin/activate
python3 receiver.py
```

Expected output:

```text
CoAP receiver listening on coap://0.0.0.0:5683
```

---

## Run sender

On sender Pi:

```bash
source venv/bin/activate
python3 sender.py
```

Expected output:

```text
[CoAP] Starting sender
[CoAP] Sending to:
  coap://###.###.###.###:5683/office/pi1/image
```

---

# Test Cases

## Case 1: One Sender to One Receiver

### Architecture

```text
Pi 1  --->  Receiver 1
```

### Sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Collect coap_receiver_results.csv
```

---

## Case 2: One Sender to Two Receivers

### Architecture

```text
          ---> Receiver 1
Pi 1
          ---> Receiver 2
```

### Sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    },
    {
        "ip": "###.###.###.###",
        "port": 5684,
        "path_segments": ["office", "pi2", "image"]
    }
]
```

### Receivers

Receiver 1:

```python
PORT = 5683
PATH_SEGMENTS = ["office", "pi1", "image"]
```

Receiver 2:

```python
PORT = 5684
PATH_SEGMENTS = ["office", "pi2", "image"]
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start receiver.py on Receiver 2
3. Start sender.py on Pi 1
4. Collect CSV files from both receivers
```

---

## Case 3: One Sender to Three Receivers

### Architecture

```text
          ---> Receiver 1
Pi 1      ---> Receiver 2
          ---> Receiver 3
```

### Sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    },
    {
        "ip": "###.###.###.###",
        "port": 5684,
        "path_segments": ["office", "pi2", "image"]
    },
    {
        "ip": "###.###.###.###",
        "port": 5685,
        "path_segments": ["office", "pi3", "image"]
    }
]
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

Both senders use the same receiver address.

### Sender 1 and Sender 2

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Start sender.py on Pi 2
4. Collect CSV file from Receiver 1
```

The receiver measures combined traffic from both senders.

---

## Case 5: Two Senders to Two Receivers

### Architecture

```text
Pi 1  --->  Receiver 1

Pi 2  --->  Receiver 2
```

This is two independent CoAP pipelines.

### Pi 1 sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]
```

### Pi 2 sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5684,
        "path_segments": ["office", "pi2", "image"]
    }
]
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start receiver.py on Receiver 2
3. Start sender.py on Pi 1
4. Start sender.py on Pi 2
5. Collect CSV files from both receivers
```

---

## Case 6: Three Senders to One Receiver

### Architecture

```text
Pi 1  --->
Pi 2  --->  Receiver 1
Pi 3  --->
```

All three senders use the same receiver address.

### Sender configuration on all Pis

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]
```

### Run order

```text
1. Start receiver.py on Receiver 1
2. Start sender.py on Pi 1
3. Start sender.py on Pi 2
4. Start sender.py on Pi 3
5. Collect CSV file from Receiver 1
```

The receiver measures total received traffic from all three senders.

---

## Case 7: Three Senders to Three Receivers

### Architecture

```text
Pi 1  --->  Receiver 1

Pi 2  --->  Receiver 2

Pi 3  --->  Receiver 3
```

This is three independent CoAP pipelines.

### Pi 1 sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5683,
        "path_segments": ["office", "pi1", "image"]
    }
]
```

### Pi 2 sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5684,
        "path_segments": ["office", "pi2", "image"]
    }
]
```

### Pi 3 sender

```python
COAP_SERVERS = [
    {
        "ip": "###.###.###.###",
        "port": 5685,
        "path_segments": ["office", "pi3", "image"]
    }
]
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

# Output Results

Each receiver creates:

```text
coap_receiver_results.csv
```

The file contains:

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

Example receiver output:

```text
Loop Results
Total images: 50
Total size: 2.9 MB
Images/sec: 5.00
MB/sec: 0.29
Images deleted.
```

