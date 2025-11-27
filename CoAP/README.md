
# CoAP-Based Image Transmission Experiment

## 1. Experiment Overview

In this experiment, we investigated the performance limitations of a CoAP-based image
transmission pipeline from multiple Raspberry Pi devices (publishers) to worker nodes
(subscribers) within a local network.

The main objective was to determine whether the network medium (**Wi-Fi vs. LAN**) or
the **CoAP protocol / software stack** serves as the primary bottleneck in achieving
high-throughput image delivery.

Each Raspberry Pi captured **480p JPEG images (~60–70 KB)**.
Images were transmitted via CoAP at varying rates and configurations, and **reception
rates were measured at worker nodes** under different network and broker arrangements
(e.g., different multiple factors, different numbers of publishers, different network
links).

This repository contains two main scripts:

* `Image_Receiver.py` – CoAP **image receiver** (worker node).
* `Image_Sender.py` – CoAP **image sender / image capture** (Raspberry Pi publisher).  

---

## 2. Scripts and Their Roles

### 2.1 `Image_Receiver.py` – CoAP Image Receiver (Worker Node)

This script implements a **CoAP server** that listens for image uploads and saves each
received JPEG to disk while measuring the **incoming image rate (images per second)**. 

**Key functionality:**

* Creates a directory called `received_images` and stores all received JPEG files there
  using timestamp-based filenames. 

* Exposes a CoAP resource at the path:

  ```text
  coap://<worker-ip>:5683/office/pi1/image # "office/pi1/image" This can be any of your choice.
  ```

  This is defined by:

  ````python
  root.add_resource(["office", "pi1", "image"], image_resource)
  ``` :contentReference[oaicite:4]{index=4}  

  ````

* On each **CoAP PUT**:

  1. Reads the raw JPEG bytes from `request.payload`.
  2. Saves them as `received_images/img_<timestamp_ns>.jpg`.
  3. Increments an internal counter and, approximately once per second, prints:

     * Number of images received in that interval.
     * Images per second (`img/s`) as a throughput metric. 
  4. Responds with CoAP status `2.04 CHANGED` and payload `OK` if successful. 

* The server binds to **all interfaces** on the default CoAP port `5683`:

  ````python
  await aiocoap.Context.create_server_context(root, bind=("0.0.0.0", 5683))
  ``` :contentReference[oaicite:7]{index=7}  

  ````

* Runs indefinitely until killed.

In other words, this script is the **subscriber / worker node endpoint** that collects
images and logs their arrival rate.

---

### 2.2 `Image_Sender.py` – CoAP Image Sender & Image Capture (Raspberry Pi)

This script runs on a **Raspberry Pi (or any camera node)**. It:

* Captures frames from a local camera at 640×480.
* Encodes each frame as a JPEG.
* Sends the same JPEG **multiple times** to a worker node (CoAP server) using PUT
  requests.
* Logs timing for:

  * Capture time.
  * JPEG encoding time.
  * CoAP PUT time.
  * Total loop time. 

**Key configuration fields:** 

```python
SERVER_IP = "192.168.1.#"   # IP of worker node running Image_Receiver.py
SERVER_PORT = 5683            # CoAP port (default)

PATH_SEGMENTS = ["office", "pi1", "image"]  # "key" (resource path) "Can be any of your choice but both sender and receiver must have same key.

REPLICAS = #                # Usually 1 (single URI)
MULTIPLY_FACTOR = #          # Sends the same JPEG this many times per loop
RUN_DURATION = #             # Number of seconds to run the experiment
```

* `SERVER_IP` – **must be set** to the IP address of the worker node running
  `Image_Receiver.py`.
* `PATH_SEGMENTS` – combined to form the CoAP path `/office/pi1/image`. This is the
  effective **“key”** or resource name and must match what the receiver uses. 
* `MULTIPLY_FACTOR` – **main experimental knob**: sends each captured image `x` times
  to stress the CoAP stack and/or network.
* `RUN_DURATION` – determines how long the script will run before auto-stopping.

**High-level loop per image:** 

1. **Capture frame** from the camera.
2. **Encode** frame as JPEG with quality 95.
3. **Send** `MULTIPLY_FACTOR` CoAP PUT requests with this JPEG to the worker URI(s).
4. **Optionally save** a local copy if `SAVE_TO_DISK = True`.
5. Log timing and loop statistics.
6. Sleep for a very short interval (`await asyncio.sleep(0.001)`) to maximize throughput
   while yielding control to the event loop.

This script is essentially the **publisher** that generates the load and drives
experiments by varying `MULTIPLY_FACTOR` and network conditions (Wi-Fi vs. LAN, etc.).

---

## 3. System Requirements

### 3.1 Hardware

* One or more **Raspberry Pi devices** (publishers) with a camera:

  * Raspberry Pi Camera Module or USB webcam supported by OpenCV.
* One or more **worker nodes** (subscribers):

  * Could be another Pi, a desktop, or a server on the same LAN/Wi-Fi network.

### 3.2 Software

* **Operating system**: Any Linux-based system (e.g., Raspberry Pi OS, Ubuntu).
* **Python**:

  * Python **3.10+ recommended** (Python 3.8+ should also work).
* **Tools**:

  * `python3`, `pip`, and `venv` (for virtual environments).

---

## 4. Initial Setup (Sender & Receiver)

You should perform the following steps on **every device** involved in the experiment:

* All Raspberry Pi publishers.
* All worker nodes running `Image_Receiver.py`.

### 4.1 Update & upgrade the system

On each machine:

```bash
sudo apt update
sudo apt upgrade -y
```

This ensures the OS packages are up to date.

### 4.2 Ed venv are insnsure Python antalled

On Debian/Ubuntu/Raspberry Pi OS:

```bash
sudo apt install -y python3 python3-pip python3-venv
```

Verify versions:

```bash
python3 --version
pip3 --version
```

---

## 5. Python Virtual Environment & Dependencies

From here, assume you are in your project directory on each machine (e.g., `/home/pi/coap-experiment`).

1. Copy both scripts into this directory:

   * `Image_Receiver.py`
   * `Image_Sender.py` (this is your camera/image capture script).

2. (Optional but recommended) Place a `Requirements.txt` file alongside them containing at least:

   ```text
   aiocoap
   opencv-python-headless
   ```

   You may add other packages as needed.

### 5.1 Create or recreate the virtual environment

```bash
python3 -m venv env
```

### 5.2 Activate the virtual environment

```bash
source env/bin/activate
```

You should see `(env)` at the beginning of your shell prompt.

### 5.3 Confirm you’re inside the venv

```bash
which python
which pip
```

They should point to paths inside your project’s `env/` directory, e.g.:

```text
/home/pi/coap-experiment/env/bin/python
/home/pi/coap-experiment/env/bin/pip
```

### 5.4 Install dependencies

Inside the activated venv:

```bash
# Upgrade pip
pip install --upgrade pip

# Install from Requirements.txt if available
pip install -r Requirements.txt

# OR at minimum, install key packages manually:
pip install aiocoap opencv-python-headless
```

Repeat this setup on **all** machines: each Raspberry Pi and each worker node.

---

## 6. Configuration for Experiments

### 6.1 Receiver configuration (`Image_Receiver.py`)

In most cases, you **do not need to modify** `Image_Receiver.py`. It:

* Listens on `0.0.0.0:5683` (all interfaces).
* Exposes the CoAP resource at `/office/pi1/image`. 

Only change this if you want:

* A different path (then you must also update `PATH_SEGMENTS` in `Image_Sender.py`).
* A different port (then adjust `SERVER_PORT` in `Image_Sender.py` accordingly).

### 6.2 Sender configuration (`Image_Sender.py` / Image capture script)

This is where you make **most** of the changes for experiments. 

```python
SERVER_IP = "192.168.x.y"   # change this to the worker node’s IP
SERVER_PORT = 5683          # must match the receiver’s port

PATH_SEGMENTS = ["office", "pi1", "image"]  # must match receiver's key/path

REPLICAS = #

MULTIPLY_FACTOR = #        # experimental knob
RUN_DURATION = #
```

#### IP & Key Matching

For each experiment, **IP and key must match** between sender and worker node:

* `SERVER_IP` on each Raspberry Pi must equal the worker node’s IP address.
* `PATH_SEGMENTS` on the sender must match the resource segments used in
  `Image_Receiver.py`:

  ```python
  root.add_resource(["office", "pi1", "image"], image_resource)
  ```

  → This corresponds to the “key” `/office/pi1/image`.

If you ever change the receiver path (e.g., `["lab", "node1", "cam"]`), you must set:

```python
PATH_SEGMENTS = ["lab", "node1", "cam"]
```

on **all senders** targeting that worker node.

#### Delay / Sleep between loops

To maximize throughput, we keep the sleep **as small as possible**. The sender currently ends each loop with:

````python
await asyncio.sleep(0.001)
``` :contentReference[oaicite:14]{index=14}  

- This is a **1 ms delay**, effectively minimal, just to allow the event loop to process other tasks.
- For all experiments, **keep this delay at 0.001** to push for maximum frame rate from the camera & sender side.

---

## 7. Using `MULTIPLY_FACTOR` for Bottleneck Analysis

The primary experimental knob is:

```python
MULTIPLY_FACTOR = <integer>
````

This controls how many times the **same JPEG** is sent for each captured frame. 

* When `MULTIPLY_FACTOR = 1`:

  * Each captured image is sent once per URI.
  * This approximates the baseline image streaming rate.

* When you increase `MULTIPLY_FACTOR` (e.g., 4, 8, 16, 32, ...):

  * The load on the CoAP stack and network increases proportionally.
  * The **camera capture rate stays roughly the same**, but the **number of CoAP PUTs per second increases**, stressing:

    * CoAP server (worker node).
    * CoAP client (sender).
    * Network (Wi-Fi/LAN).

By systematically increasing `MULTIPLY_FACTOR` under different conditions (Wi-Fi vs. LAN, multiple publishers vs. single publisher), you can observe:

* At what point the **receiver’s images/sec** stops scaling and starts to plateau or drop.
* Whether errors or timeouts appear on the sender.
* Whether the bottleneck appears to be:

  * CPU (CoAP processing),
  * network bandwidth / contention,
  * or camera I/O.

---

## 8. Running the Experiment

### 8.1 On the Worker Node (Receiver)

1. Activate the venv:

   ```bash
   cd /path/to/coap-experiment
   source env/bin/activate
   ```

2. Start the CoAP image server:

   ```bash
   python Image_Receiver.py
   ```

3. You should see:

   ```text
   [CoAP] Image server listening on coap://0.0.0.0:5683/office/pi1/image
   ```

4. As images arrive, the receiver prints throughput:

   ```text
   Received 120 images in 1.00s -> 120.0 img/s
   ```

   Saved images appear under `received_images/`. 

### 8.2 On Each Raspberry Pi (Sender / Publisher)

1. Activate the venv:

   ```bash
   cd /path/to/coap-experiment
   source env/bin/activate
   ```

2. Edit `Image_Sender.py`:

   * Set `SERVER_IP` to the **IP of the worker node**.
   * Ensure `SERVER_PORT` and `PATH_SEGMENTS` match the receiver.
   * Set `MULTIPLY_FACTOR` to your desired test value.
   * Set `RUN_DURATION` (e.g., 30, 60, 300 seconds).

3. Run the sender:

   ```bash
   python Image_Sender.py
   ```

4. The script prints timings like:

   ```text
   CoAP PUTs: 12 | Capture: 0.0200s | Encode: 0.0080s |
   PUTs: 0.0500s | Total loop: 0.0780s
   ```

5. After `RUN_DURATION` seconds, the sender stops automatically, releases the camera, and exits. 

---

## 9. Interpreting Results

* **Receiver logs** (images per second) show how many images actually reach the worker.
* **Sender logs** (timing per loop) show:

  * How much time is spent capturing, encoding, and sending.
  * Whether CoAP PUTs dominate the loop (indicating protocol/network overhead).
* By running experiments:

  * Over Wi-Fi vs. wired LAN.
  * With different `MULTIPLY_FACTOR` values.
  * With 1 vs. multiple Raspberry Pis.

You can compare:

* Whether throughput is limited by **network medium** (e.g., Wi-Fi saturating) or by
  the **CoAP stack** (CPU, implementation overhead, etc.).

---

## 10. Summary of What You Need to Change

For each experiment, you **only need to touch a few parameters in the sender**:

1. In `Image_Sender.py` (image capture / sender script):

   * `SERVER_IP` → IP of the worker node.
   * `PATH_SEGMENTS` → must match the receiver’s key/resource path.
   * `MULTIPLY_FACTOR` → main experimental variable to scale the number of CoAP PUTs per image.
   * `RUN_DURATION` → how long you want the run.

2. Keep:

   * `await asyncio.sleep(0.001)` as-is, to keep the delay minimal and push maximum image generation.
   * Receiver script (`Image_Receiver.py`) unchanged, unless you explicitly want a different port or path.


