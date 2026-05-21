# Kafka Image Transmission Benchmark

## Overview

This project is used to test image transmission performance using Apache Kafka between Raspberry Pis and receiver systems over a network.

The system captures images from sender devices (Raspberry Pis), sends them through Kafka, and the receivers measure:

* How many images are received
* Images received per second
* Data received per second (MB/s)
* Stream stability over 50 repeated tests

The receiver automatically:

* Saves incoming images
* Measures throughput
* Stores benchmark results in CSV format
* Deletes images after every loop to keep storage clean

---

# Project Structure

## Sender

The sender:

* Captures images
* Converts images to Base64
* Sends images to Kafka topics

## Receiver

The receiver:

* Subscribes to Kafka topics
* Receives image messages
* Decodes and saves images
* Calculates benchmark statistics
* Writes results into CSV files

## Kafka Broker

Kafka acts as the middle layer between senders and receivers.

```text
Sender → Kafka Broker → Receiver
```

---

# Requirements

## Install Python Packages

Run on sender and receiver systems:

```bash
pip install kafka-python opencv-python numpy
```

---

# Kafka Setup

## Install Java

```bash
sudo apt install openjdk-11-jdk -y
```

Verify:

```bash
java -version
```

---

# Kafka Broker Configuration

Edit:

```bash
~/kafka/config/server.properties
```

Use:

```properties
broker.id=0

listeners=PLAINTEXT://0.0.0.0:9092

advertised.listeners=PLAINTEXT://###.###.###.###:9092

log.dirs=/tmp/kafka-logs

zookeeper.connect=localhost:2181
```

Replace:

```text
###.###.###.###
```

with the broker machine IP.

---

# Start Kafka

## Start Zookeeper

```bash
cd ~/kafka
bin/zookeeper-server-start.sh config/zookeeper.properties
```

## Start Kafka Broker

Open another terminal:

```bash
cd ~/kafka
bin/kafka-server-start.sh config/server.properties
```

---

# Verify Kafka Is Running

```bash
ss -ltnp | grep 9092
```

Expected:

```text
LISTEN ... *:9092
```

Test connection:

```bash
nc -vz ###.###.###.### 9092
```

Expected:

```text
succeeded
```

---

# Receiver Benchmark Output

The receiver automatically creates:

```text
kafka_receiver_results.csv
```

The CSV contains:

* Loop number
* Images received
* MB received
* Images per second
* MB per second
* Timestamp
* Status

---

# Important Receiver Settings

## Receiver Group IDs

For one sender sending to multiple receivers:

Each receiver must use a different `group_id`.

Example:

Receiver 1:

```python
group_id="receiver_1_group"
```

Receiver 2:

```python
group_id="receiver_2_group"
```

Receiver 3:

```python
group_id="receiver_3_group"
```

If the same group ID is used, Kafka will split messages between receivers.

---

# Sender Configuration

Main settings:

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"

TOPIC_BASE = "images_pi1"

REPLICAS = 1

MULTIPLY_FACTOR = 1
```

---

# Receiver Configuration

Main settings:

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"

TOPIC_BASE = "images_pi1"

REPLICAS = 1
```

---

# Test Cases

---

# Case 1 — One Sender to One Receiver

## Architecture

```text
1 Sender → 1 Kafka Broker → 1 Receiver
```

## Sender

```python
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

## Receiver

```python
group_id="receiver_1_group"
```

---

# Case 2 — One Sender to Two Receivers

## Architecture

```text
                → Receiver 1
Sender → Broker
                → Receiver 2
```

## Sender

```python
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

## Receiver 1

```python
group_id="receiver_1_group"
```

## Receiver 2

```python
group_id="receiver_2_group"
```

Important:

* Both receivers must use different group IDs
* Both receivers receive the full stream

---

# Case 3 — One Sender to Three Receivers

## Architecture

```text
                → Receiver 1
Sender → Broker → Receiver 2
                → Receiver 3
```

## Sender

```python
REPLICAS = 1
MULTIPLY_FACTOR = 1
```

## Receivers

Receiver 1:

```python
group_id="receiver_1_group"
```

Receiver 2:

```python
group_id="receiver_2_group"
```

Receiver 3:

```python
group_id="receiver_3_group"
```

---

# Case 4 — Two Senders to One Receiver

## Architecture

```text
Sender 1 ─┐
          ├→ Broker → Receiver
Sender 2 ─┘
```

## Sender 1

```python
TOPIC_BASE = "images_pi1"
```

## Sender 2

```python
TOPIC_BASE = "images_pi1"
```

## Receiver

```python
TOPIC_BASE = "images_pi1"
```

The receiver measures the combined stream from both senders.

---

# Case 5 — Two Senders to Two Receivers

## Architecture

Two independent pipelines:

```text
Sender 1 → Broker 1 → Receiver 1

Sender 2 → Broker 2 → Receiver 2
```

Each receiver runs its own Kafka broker.

## Sender 1

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Receiver 1

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Sender 2

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Receiver 2

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

---

# Case 6 — Three Senders to One Receiver

## Architecture

```text
Sender 1 ─┐
Sender 2 ─┼→ Broker → Receiver
Sender 3 ─┘
```

## All Senders

Use the same:

```python
TOPIC_BASE = "images_pi1"
```

## Receiver

Subscribes to the same topic:

```python
TOPIC_BASE = "images_pi1"
```

The receiver measures the combined traffic from all three senders.

---

# Case 7 — Three Senders to Three Receivers

## Architecture

Three independent pipelines:

```text
Sender 1 → Broker 1 → Receiver 1

Sender 2 → Broker 2 → Receiver 2

Sender 3 → Broker 3 → Receiver 3
```

Each receiver runs its own Kafka broker.

## Sender 1

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Receiver 1

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Sender 2

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Receiver 2

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Sender 3

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

## Receiver 3

```python
KAFKA_BOOTSTRAP = "###.###.###.###:9092"
```

---

# Running the Tests

Recommended order:

## On Receiver Machines

1. Start Zookeeper
2. Start Kafka broker
3. Start receiver.py

## On Sender Devices

4. Start sender.py

---

# Cleaning Kafka Logs

Kafka logs may fill storage over time.

To clean logs:

```bash
rm -rf /tmp/kafka-logs/*
```

Check storage:

```bash
df -h
```

---

# Notes

* Kafka uses a broker-based architecture
* Senders do not connect directly to receivers
* All communication goes through Kafka brokers
* Different receiver `group_id`s are required for broadcast-style receiving
* The receiver automatically deletes images after every benchmark loop

---

# Result

The benchmark measures:

* Total images received
* Images per second
* Total MB received
* MB per second
* Stability across 50 repeated runs
