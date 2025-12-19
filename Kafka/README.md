Nice, now we know the Pi is **Debian 12 (bookworm)**, so I’ll write the README for that setup and what you already did on the NUC.

Below is a **teaching-style README** you can save as `README.md` and reuse on other systems.

---

# Image Streaming with Kafka (Pi → NUC)

This project sends camera images from a **Raspberry Pi (producer)** to a **receiver machine (Kafka broker + consumer, e.g. NUC)** using **Apache Kafka** and **Python**.

We’ll go step by step:

* Set up Kafka (ZooKeeper + broker) on the **receiver**
* Make Kafka **start automatically** with `systemd`
* Set up Python virtual environments on **both** machines
* Run the **receiver script** on the NUC
* Run the **camera producer script** on the Pi
* Troubleshooting & sanity checks

---

## 0. Overview / Architecture

* **Pi (producer)**

  * OS: Debian 12 (bookworm)
  * Runs `image_capture_kafka.py`
  * Uses OpenCV to grab frames from the USB camera
  * Sends Base64-encoded JPEG images to Kafka topic `images_pi1`

* **NUC or other Linux machine (receiver)**

  * Runs **ZooKeeper + Kafka broker** (single node)
  * Kafka topic: `images_pi1`
  * Python script `images_receiver_kafka.py` consumes the images and saves them under `./analyzed_images/`

For multiple systems, you can repeat the “Pi setup” on each sender and adjust the topic name if needed (e.g., `images_pi2`, etc.).

---

## 1. Prerequisites

### 1.1. On the Receiver (Kafka server + consumer)

* Linux (Debian / Ubuntu is fine)
* User account that owns Kafka, e.g. `nuc`
* Java installed (OpenJDK 17+ or 21)
* Kafka downloaded and extracted in:

```bash
/home/nuc/kafka
```

You already have **Kafka 3.8.0** under `~/kafka`. For a new machine, roughly:

```bash
cd ~
wget https://downloads.apache.org/kafka/3.8.0/kafka_2.13-3.8.0.tgz
tar -xzf kafka_2.13-3.8.0.tgz
mv kafka_2.13-3.8.0 kafka
```

### 1.2. On the Pi (producer)

* OS: Debian 12 (bookworm) on Raspberry Pi
* USB camera (Logitech BRIO in your case)
* Network connectivity to the Kafka server (e.g., 192.168.1.177)

---

## 2. Configure & Run Kafka on the Receiver

### 2.1. Adjust Kafka `server.properties`

We want Kafka to listen on **port 9092** and advertise its **LAN IP** so that other machines (Pi) can connect.

Edit:

```bash
nano /home/nuc/kafka/config/server.properties
```

Find these lines (they may be commented):

```properties
#listeners=PLAINTEXT://:9092
#advertised.listeners=PLAINTEXT://your.host.name:9092
```

Change them to something like:

```properties
listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://192.168.1.177:9092
```

* `listeners=PLAINTEXT://:9092`
  → Kafka listens on **all interfaces** on port 9092.
* `advertised.listeners=PLAINTEXT://192.168.1.177:9092`
  → This is the IP that **clients use to reach the broker**.
  Replace `192.168.1.177` with the **actual IP** of your Kafka server on the LAN.

Save and exit.

---

## 3. Create systemd service for ZooKeeper

We want ZooKeeper to **start automatically at boot**.

### 3.1. Create unit file

```bash
sudo nano /etc/systemd/system/zookeeper.service
```

Paste:

```ini
[Unit]
Description=Apache ZooKeeper Server
After=network.target

[Service]
Type=simple
User=nuc
Group=nuc
WorkingDirectory=/home/nuc/kafka
ExecStart=/home/nuc/kafka/bin/zookeeper-server-start.sh /home/nuc/kafka/config/zookeeper.properties
ExecStop=/home/nuc/kafka/bin/zookeeper-server-stop.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Important:**

* `User` and `Group` must match the Linux user that owns `/home/nuc/kafka`.
  If you use another username, change `nuc` accordingly.
* `WorkingDirectory` must point to the Kafka folder.

### 3.2. Enable and start ZooKeeper

```bash
sudo systemctl daemon-reload
sudo systemctl enable zookeeper
sudo systemctl start zookeeper
sudo systemctl status zookeeper
```

Expected:

* `Active: active (running)`
* No big red errors

If there are errors, check logs:

```bash
journalctl -u zookeeper -xe
```

---

## 4. Create systemd service for Kafka Broker

Now we make Kafka also start automatically, **after ZooKeeper**.

### 4.1. Create unit file

```bash
sudo nano /etc/systemd/system/kafka.service
```

Paste:

```ini
[Unit]
Description=Apache Kafka Broker
After=network.target zookeeper.service
Requires=zookeeper.service

[Service]
Type=simple
User=nuc
Group=nuc
WorkingDirectory=/home/nuc/kafka
ExecStart=/home/nuc/kafka/bin/kafka-server-start.sh /home/nuc/kafka/config/server.properties
ExecStop=/home/nuc/kafka/bin/kafka-server-stop.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Again, adjust `User`, `Group`, and `WorkingDirectory` as needed.

### 4.2. Enable and start Kafka

```bash
sudo systemctl daemon-reload
sudo systemctl enable kafka
sudo systemctl start kafka
sudo systemctl status kafka
```

Expected:

* `Active: active (running)`

### 4.3. Verify Kafka is listening and topic exists

List topics:

```bash
cd ~/kafka
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

You should see at least:

```text
__consumer_offsets
images_pi1
```

If `images_pi1` does not exist yet:

```bash
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic images_pi1 --partitions 1 --replication-factor 1
```

Then list again to confirm.

### 4.4. Test from Pi: network connectivity

On the **Pi**:

```bash
nc -vz 192.168.1.177 9092
```

Expected:

```text
Connection to 192.168.1.177 9092 port [tcp/*] succeeded!
```

If it says “Connection refused” or “timed out”, then Kafka is not reachable (check firewall, IP, services).

---

## 5. Python Environment on the Receiver (consumer)

We’ll create a virtual environment and install the needed Python packages.

Example folder (use whatever you like):

```bash
mkdir -p "~/Desktop/Images Transmission Buses/Kafka"
cd "~/Desktop/Images Transmission Buses/Kafka"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install kafka-python opencv-python
```

Now put `images_receiver_kafka.py` in this folder (you already have it).
Make sure its topic matches the one you created:

```python
TOPICS = ["images_pi1"]
```

### 5.1. Run the receiver

From that folder:

```bash
source venv/bin/activate
python3 images_receiver_kafka.py
```

Expected output (similar to what you saw):

```text
🚀 Kafka image receiver subscribed to topics: ['images_pi1']
    Send JSON messages with keys: topic, filename, image_b64
✅ Image saved: ./analyzed_images/images_pi1_YYYYMMDD_HHMMSS_xxxxxx.jpg
...
```

* The script should create an `analyzed_images/` folder and save `.jpg` files inside.

Keep this terminal open while testing from the Pi.

---

## 6. Python Environment on the Raspberry Pi (producer)

Now we prepare the Pi.

### 6.1. Ensure the camera works (you already did this, but for documentation)

Install tools:

```bash
sudo apt update
sudo apt install -y v4l-utils
```

List devices:

```bash
v4l2-ctl --list-devices
```

You saw something like:

```text
Logitech BRIO (usb-xhci-hcd.0-1):
    /dev/video0
    /dev/video1
    /dev/video2
    /dev/video3
```

We tested indices and found **index 0 works**.

### 6.2. Create virtual environment

Choose folder, e.g.:

```bash
cd ~/Project2.0/Kafka
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install kafka-python opencv-python
```

### 6.3. Quick camera sanity test

Run this once:

```bash
source venv/bin/activate
python3 - << 'EOF'
import cv2

cap = cv2.VideoCapture(0)   # index 0 (we know it works)

if not cap.isOpened():
    print("❌ Camera failed to open.")
else:
    print("✅ Camera opened successfully.")
    ret, frame = cap.read()
    if ret:
        print("✅ Captured a frame successfully!")
        print("Frame shape:", frame.shape)
        cv2.imwrite("test_capture.jpg", frame)
        print("✅ Saved test_capture.jpg in current directory.")
    else:
        print("❌ Failed to read a frame.")

cap.release()
EOF
```

Expected:

* `✅ Camera opened successfully.`
* `✅ Captured a frame successfully!`
* A file `test_capture.jpg` appears in your current directory.

You can inspect it with an image viewer to confirm it’s okay.

---

## 7. Configure and Run the Kafka Producer on the Pi

Open your producer script:

```bash
cd ~/Project2.0/Kafka
nano image_capture_kafka.py
```

Make sure the **bootstrap server** points to your broker IP (receiver):

```python
KAFKA_BOOTSTRAP = "192.168.1.177:9092"  # IP of Kafka server
TOPIC_BASE = "images_pi1"
REPLICAS = 1
MULTIPLY_FACTOR = 2     # how many times to send the same image per topic
RUN_DURATION = 10       # seconds to run
```

Important bits:

* `cv2.VideoCapture(0)` – uses the working camera index.
* `KAFKA_BOOTSTRAP` – must match `advertised.listeners` (IP:port) on the broker.
* `TOPIC_BASE` – must match the Kafka topic (`images_pi1`).

### 7.1. Run the producer

From the Pi:

```bash
cd ~/Project2.0/Kafka
source venv/bin/activate
python3 image_capture_kafka.py
```

Expected:

* The script runs for `RUN_DURATION` seconds and prints:

```text
Run duration of 10 seconds reached. Stopping.
```

* No Kafka errors in the terminal (if there are, see troubleshooting below).
* On the receiver side, you should see a stream of:

```text
✅ Image saved: ./analyzed_images/images_pi1_YYYYMMDD_...
```

And new image files appear in `analyzed_images/`.

---

## 8. What Is Now Automated?

Using the `systemd` services:

* **ZooKeeper** starts automatically at boot (`zookeeper.service`)
* **Kafka broker** starts automatically at boot (`kafka.service`, which depends on ZooKeeper)

So now, **after a reboot**, you don’t have to manually:

* Run `zookeeper-server-start.sh`
* Run `kafka-server-start.sh`

You can simply:

* On the receiver: run `images_receiver_kafka.py` whenever you want to capture
* On the Pi: run `image_capture_kafka.py` whenever you want to send images

Optional (future): you could also make **systemd services for the Python scripts** to run them automatically, but for now you’re already in a good state where all Kafka infrastructure is auto.

---

## 9. Troubleshooting

### 9.1. Error: `NoBrokersAvailable` in Python

Common causes:

1. Kafka service not running

   * Check:

     ```bash
     systemctl status kafka
     ```

2. `KAFKA_BOOTSTRAP` IP doesn’t match `advertised.listeners`

   * Check `server.properties` and your Pi script:

     * `advertised.listeners=PLAINTEXT://192.168.1.177:9092`
     * `KAFKA_BOOTSTRAP = "192.168.1.177:9092"`

3. Firewall blocking port 9092

   * Test from Pi:

     ```bash
     nc -vz 192.168.1.177 9092
     ```

### 9.2. Error: `ECONNREFUSED` in Kafka logs

* Means something tried to connect to a port where no service was listening.
* Check if Kafka started **before** you changed `server.properties`.
  If in doubt, restart:

  ```bash
  sudo systemctl restart zookeeper
  sudo systemctl restart kafka
  ```

### 9.3. Receiver script doesn’t save images

* Make sure directory `analyzed_images/` is writable by your user.
* Add some debugging prints in `images_receiver_kafka.py` to dump the topic and filename.
* Make sure the consumer is subscribed to `images_pi1` and not some other topic.

### 9.4. Camera errors on the Pi

* If you see `can't open camera by index`:

  * Double-check `v4l2-ctl --list-devices`
  * Retry the quick test script with other indexes (0–3) until one works.
  * Update firmware / check USB cable / try another port.

---

## 10. Adapting to Multiple Systems

For **multiple Pis**:

* Repeat **Section 6–7** on each Pi.
* You can either:

  * Use the **same Kafka topic** (`images_pi1`) for all Pis (then images mix together), or
  * Give each Pi its own topic (`images_pi2`, `images_pi3`, etc.) and update:

    ```python
    TOPIC_BASE = "images_pi2"
    ```
* On the receiver, your consumer can:

  * Subscribe to a **list** of topics: `["images_pi1", "images_pi2", ...]`, or
  * Run multiple instances of the consumer script, one per topic.

---

