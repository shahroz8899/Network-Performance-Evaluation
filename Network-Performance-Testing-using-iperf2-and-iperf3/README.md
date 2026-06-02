# iPerf3 Network Bandwidth Benchmarking Framework

## Overview

This project provides a repeatable framework for measuring the **raw network bandwidth** between distributed systems using **iPerf3**.

Unlike the Kafka, HTTP, MQTT, CoAP, and Zenoh experiments, which transfer actual images and measure application-level performance, this framework measures the **maximum achievable network throughput** between nodes.

The goal is to establish a **network baseline** and answer questions such as:

* What is the maximum available bandwidth?
* How stable is the network over repeated runs?
* How does bandwidth change when multiple senders or receivers are active simultaneously?
* What is the aggregate throughput of the system?

---

# Experiment Goals

This benchmark measures:

### Sender Side

* Total data transmitted (MB)
* Throughput (Mbps)
* Throughput (MB/s)
* TCP retransmissions

### Receiver Side

* Total data received (MB)
* Throughput (Mbps)
* Throughput (MB/s)

### Collective Metrics

For multi-receiver experiments:

* Total transmitted data
* Total received data
* Aggregate throughput
* Aggregate retransmissions

---

# Test Environment

The framework supports:

### WiFi Experiments

* Case 1: One Sender → One Receiver
* Case 2: One Sender → Two Receivers
* Case 3: One Sender → Three Receivers
* Case 4: Two Senders → One Receiver
* Case 5: Two Senders → Two Receivers
* Case 6: Three Senders → One Receiver
* Case 7: Three Senders → Three Receivers

### LAN Experiments

The same seven configurations are repeated over LAN.

Total:

```text
7 WiFi Tests
+
7 LAN Tests

=
14 Total Experiments
```

---

# Directory Structure

```text
iPerf3/
│
├── sender.py
├── receiver.py
├── iperf3_parallel_results.csv
├── README.md
└── venv/
```

---

# Requirements

Install iPerf3.

### Ubuntu

```bash
sudo apt update
sudo apt install iperf3
```

Verify:

```bash
iperf3 --version
```

Example:

```text
iperf 3.16
```

---

# Creating a Virtual Environment

Although the sender uses only standard Python libraries, it is recommended to create a virtual environment.

```bash
mkdir iperf3-benchmark

cd iperf3-benchmark

python3 -m venv venv
```

Activate:

```bash
source venv/bin/activate
```

Verify:

```bash
which python
```

Example:

```text
.../venv/bin/python
```

---

# Receiver Setup

The receiver starts one or more iPerf3 servers.

Example:

```python
IPERF_PORTS = [
    5201,
]
```

Start:

```bash
python3 receiver.py
```

Example output:

```text
Starting iperf3 server on port 5201

iperf3 receiver is running.
Press CTRL+C to stop.
```

---

# Sender Setup

Configure targets:

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    },
]
```

Start:

```bash
python3 sender.py
```

---

# Benchmark Parameters

```python
TEST_DURATION = 10
NUMBER_OF_LOOPS = 50
PROTOCOL = "tcp"
```

Meaning:

```text
Each run lasts 10 seconds.

Each experiment repeats 50 times.

TCP is used to measure actual available bandwidth.
```

---

# Why TCP?

TCP automatically determines the maximum achievable throughput.

This provides:

```text
Actual Network Capacity
```

instead of:

```text
Artificially Limited Capacity
```

For this reason:

```python
PROTOCOL = "tcp"
```

is recommended for all experiments.

---

# CSV Output

The benchmark automatically creates:

```text
iperf3_parallel_results.csv
```

Example:

```csv
loop_number,target_name,sender_transfer_mb,sender_mbits_per_second,sender_MB_per_second,receiver_transfer_mb,receiver_mbits_per_second,receiver_MB_per_second,retransmits
1,AGX,55.38,46.45,5.54,52.54,43.71,5.25,1
```

---

# Metric Definitions

### sender_transfer_mb

Total data sent.

Example:

```text
55.38 MB
```

---

### sender_mbits_per_second

Sender throughput.

Example:

```text
46.45 Mbps
```

---

### sender_MB_per_second

Sender throughput in MB/s.

Example:

```text
5.54 MB/s
```

---

### receiver_transfer_mb

Total received data.

Example:

```text
52.54 MB
```

---

### receiver_mbits_per_second

Receiver throughput.

Example:

```text
43.71 Mbps
```

---

### receiver_MB_per_second

Receiver throughput in MB/s.

Example:

```text
5.25 MB/s
```

---

### retransmits

TCP retransmissions.

Example:

```text
1
```

Lower values indicate a more stable connection.

---

# Case 1 — One Sender → One Receiver

## Receiver

```bash
iperf3 -s -p 5201
```

or

```bash
python3 receiver.py
```

with:

```python
IPERF_PORTS = [5201]
```

## Sender

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    }
]
```

Run:

```bash
python3 sender.py
```

---

# Case 2 — One Sender → Two Receivers

## Receiver 1

```bash
iperf3 -s -p 5201
```

## Receiver 2

```bash
iperf3 -s -p 5202
```

## Sender

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    },
    {
        "ip": "###.###.###.###",
        "port": 5202,
        "name": "receiver_2"
    }
]
```

The sender runs both tests simultaneously.

CSV contains:

```text
receiver_1
receiver_2
COLLECTIVE_TOTAL
```

---

# Case 3 — One Sender → Three Receivers

## Receiver 1

```bash
iperf3 -s -p 5201
```

## Receiver 2

```bash
iperf3 -s -p 5202
```

## Receiver 3

```bash
iperf3 -s -p 5203
```

## Sender

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    },
    {
        "ip": "###.###.###.###",
        "port": 5202,
        "name": "receiver_2"
    },
    {
        "ip": "###.###.###.###",
        "port": 5203,
        "name": "receiver_3"
    }
]
```

---

# Case 4 — Two Senders → One Receiver

## Receiver

```bash
iperf3 -s -p 5201
```

## Sender 1

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver"
    }
]
```

Run:

```bash
python3 sender.py
```

## Sender 2

Run the same script simultaneously.

Both senders transmit to the same receiver.

---

# Case 5 — Two Senders → Two Receivers

Receiver 1:

```bash
iperf3 -s -p 5201
```

Receiver 2:

```bash
iperf3 -s -p 5202
```

Sender 1:

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    }
]
```

Sender 2:

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5202,
        "name": "receiver_2"
    }
]
```

Run both simultaneously.

---

# Case 6 — Three Senders → One Receiver

Receiver:

```bash
iperf3 -s -p 5201
```

Start three sender systems simultaneously.

Each sender targets:

```python
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver"
    }
]
```

---

# Case 7 — Three Senders → Three Receivers

Receiver 1:

```bash
iperf3 -s -p 5201
```

Receiver 2:

```bash
iperf3 -s -p 5202
```

Receiver 3:

```bash
iperf3 -s -p 5203
```

Sender 1:

```python
receiver_1
```

Sender 2:

```python
receiver_2
```

Sender 3:

```python
receiver_3
```

Run all senders simultaneously.

---

# WiFi Experiments

Run all seven cases over WiFi.

Store results:

```text
WiFi/
├── Case_1
├── Case_2
├── Case_3
├── Case_4
├── Case_5
├── Case_6
└── Case_7
```

---

# LAN Experiments

Reconnect systems using Ethernet.

Repeat all seven cases.

Store results:

```text
LAN/
├── Case_1
├── Case_2
├── Case_3
├── Case_4
├── Case_5
├── Case_6
└── Case_7
```

---

# Expected Outputs

For every test case:

```text
50 repetitions
CSV file
Average throughput
Average MB/s
Average Mbps
Average retransmissions
Collective throughput
```

These results can then be compared directly against:

* HTTP
* CoAP
* MQTT
* Kafka
* Zenoh

to determine how much of the available network capacity each middleware is able to utilize.
