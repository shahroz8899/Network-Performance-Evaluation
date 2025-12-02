

# 📘 **Network Performance Testing Report using iperf2 and iperf3**


---

# **1. Introduction**

Network performance evaluation is a critical part of distributed systems research, IoT networks, edge computing, and cluster communication studies.
This document provides **complete, step-by-step instructions** for conducting bandwidth tests under different scenarios:

1. **One sender → One receiver**
2. **Multiple senders → One receiver**
3. **Multiple senders → Multiple receivers**

Both **iperf3** and **iperf2** are covered:

* **iperf3** is newer, but supports **only one client per server instance**
* **iperf2** allows **multiple simultaneous connections**, ideal for multi-sender stress tests

---

# **2. Preparing the Environment**

## **2.1 Supported Operating Systems**

This guide applies to:

* Raspberry Pi OS (Debian-based)
* Ubuntu/Debian
* Linux desktops/servers

---

# **3. Installing and Removing iperf**

## **3.1 Install iperf3**

Run on any machine (Pi or server):

```bash
sudo apt update
sudo apt install iperf3 -y
```

Verify installation:

```bash
iperf3 --version
```

---

## **3.2 Install iperf2**

(needed for multi-sender tests)

```bash
sudo apt update
sudo apt install iperf -y
```

Verify:

```bash
iperf --version
```

---

## **3.3 Remove old or corrupted installations**

If you need to uninstall:

### Remove iperf3:

```bash
sudo apt remove iperf3 -y
sudo apt purge iperf3 -y
```

### Remove iperf2:

```bash
sudo apt remove iperf -y
sudo apt purge iperf -y
```

Clean unused packages:

```bash
sudo apt autoremove -y
```

---

# **4. Cleaning Old Stuck Processes (VERY IMPORTANT)**

If previous iperf instances crashed, they may still be running.

Check all iperf3 processes:

```bash
ps aux | grep iperf3
```

Kill all:

```bash
sudo killall iperf3
```

If a PID survives, kill manually:

```bash
sudo kill -9 <PID>
```

Repeat for iperf2:

```bash
sudo killall iperf
```

---

# **5. Network Scenarios and Test Procedures**

---

# **Scenario 1: One Sender → One Receiver (Single Flow)**

### Recommended: iperf3

## **5.1 Start server (receiver)**

On the receiver node:

```bash
iperf3 -s
```

It listens on port **5201**.

---

## **5.2 Start sender (client)**

On sender Pi:

```bash
iperf3 -c <receiver_ip> -t 10
```

Example:

```bash
iperf3 -c 192.168.1.135 -t 10
```

---

## **5.3 Optional parameters**

* Reverse direction (server → client):

  ```bash
  iperf3 -c <ip> -R -t 10
  ```

* Bidirectional test:

  ```bash
  iperf3 -c <ip> --bidir -t 10
  ```

---

# **Scenario 2: Multiple Senders → One Receiver**

You have **two choices**:

---

## **Option A: Using iperf2 (Best and simplest)**

iperf2 supports **multiple clients connecting to one server simultaneously**.

### **Start server once**:

```bash
iperf -s
```

### **Start clients on each Pi**:

Pi1:

```bash
iperf -c <receiver_ip> -t 10
```

Pi2:

```bash
iperf -c <receiver_ip> -t 10
```

Pi3:

```bash
iperf -c <receiver_ip> -t 10
```

All three run **at the same time**.

✔️ Measures aggregated bandwidth
✔️ Realistic stress test
✔️ No port management needed

---

## **Option B: Using iperf3 (Multiple ports required)**

Because iperf3 handles only one client at a time per port.

### Start multiple server instances on different ports:

```bash
iperf3 -s -p 5201 &
iperf3 -s -p 5202 &
iperf3 -s -p 5203 &
```

### Clients:

Pi1 → 5201

```bash
iperf3 -c <ip> -p 5201 -t 10
```

Pi2 → 5202

```bash
iperf3 -c <ip> -p 5202 -t 10
```

Pi3 → 5203

```bash
iperf3 -c <ip> -p 5203 -t 10
```

---

# **Scenario 3: Multiple Senders → Multiple Receivers**

You can use iperf2 or iperf3.

---

## **Option A: iperf2 (simplest)**

Start server on Receiver 1:

```bash
iperf -s
```

Start server on Receiver 2:

```bash
iperf -s -p 5202
```

Start sender flows from multiple Pis:

Pi1 → Receiver1:

```bash
iperf -c <R1_ip> -t 10
```

Pi2 → Receiver2:

```bash
iperf -c <R2_ip> -p 5202 -t 10
```

Pi3 → Receiver1 or Receiver2:

```bash
iperf -c <R1_ip> -t 10
```

---

## **Option B: iperf3 (port isolation required)**

For each receiver:

Receiver1:

```bash
iperf3 -s -p 5201
```

Receiver2:

```bash
iperf3 -s -p 5202
```

Senders must connect to correct port.

---

# **6. Logging Results for Reporting**

iperf allows saving data to files:

### iperf3:

```bash
iperf3 -c <ip> -t 10 --json > result1.json
```

### iperf2:

```bash
iperf -c <ip> -t 10 > sender1.txt
```

---

# **7. Troubleshooting (Most Common Issues)**

### **Error: Connection refused**

Cause: server not running
Fix:

```bash
iperf3 -s
```

---

### **Error: Server busy**

Cause: iperf3 already serving another client
Fix:

* Use iperf2
* Or use different ports

---

### **Error: Address already in use**

Kill stuck process:

```bash
sudo killall iperf3
```

---

# **8. Summary Table**

| Scenario | Recommended Tool | How many ports? | Easy? | Notes                         |
| -------- | ---------------- | --------------- | ----- | ----------------------------- |
| 1→1      | iperf3           | 1               | ✔️    | Most accurate                 |
| N→1      | iperf2           | 1               | ✔️✔️  | Best for aggregate throughput |
| N→1      | iperf3           | N ports         | ❌     | Harder to maintain            |
| N→M      | iperf2           | 1 per receiver  | ✔️✔️  | Flexible                      |
| N→M      | iperf3           | N×M ports       | ❌❌    | Only for special cases        |

---


