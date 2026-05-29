import subprocess
import json
import csv
import time
from datetime import datetime


# ===== Test Targets =====
# For one sender to one receiver: keep one target.
# For one sender to multiple receivers: uncomment/add more targets.
IPERF_TARGETS = [
    {
        "ip": "###.###.###.###",
        "port": 5201,
        "name": "receiver_1"
    },

    # {
    #     "ip": "###.###.###.###",
    #     "port": 5201,
    #     "name": "receiver_2"
    # },

    # {
    #     "ip": "###.###.###.###",
    #     "port": 5201,
    #     "name": "receiver_3"
    # },
]


# ===== Benchmark Settings =====
TEST_DURATION = 10
NUMBER_OF_LOOPS = 50

PROTOCOL = "tcp"       # tcp or udp
UDP_BITRATE = "100M"  # only used if PROTOCOL = "udp"

CSV_FILE = "iperf3_sender_results.csv"

all_results = []


def run_iperf_test(target):
    ip = target["ip"]
    port = target["port"]

    cmd = [
        "iperf3",
        "-c", ip,
        "-p", str(port),
        "-t", str(TEST_DURATION),
        "-J"
    ]

    if PROTOCOL.lower() == "udp":
        cmd.extend(["-u", "-b", UDP_BITRATE])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TEST_DURATION + 15
        )

        if result.returncode != 0:
            return {
                "status": "failed",
                "sender_transfer_mb": 0,
                "sender_mbits_per_sec": 0,
                "sender_MB_per_sec": 0,
                "receiver_transfer_mb": 0,
                "receiver_mbits_per_sec": 0,
                "receiver_MB_per_sec": 0,
                "retransmits": 0,
                "error": result.stderr.strip()
            }

        data = json.loads(result.stdout)
        end_data = data.get("end", {})

        sender = end_data.get("sum_sent", {})
        receiver = end_data.get("sum_received", {})

        sender_bytes = sender.get("bytes", 0)
        sender_bps = sender.get("bits_per_second", 0)
        receiver_bytes = receiver.get("bytes", 0)
        receiver_bps = receiver.get("bits_per_second", 0)
        retransmits = sender.get("retransmits", 0)

        # Fallback for iperf3 versions that store results inside streams
        if sender_bytes == 0 and "streams" in end_data and len(end_data["streams"]) > 0:
            stream_sender = end_data["streams"][0].get("sender", {})
            stream_receiver = end_data["streams"][0].get("receiver", {})

            sender_bytes = stream_sender.get("bytes", 0)
            sender_bps = stream_sender.get("bits_per_second", 0)
            receiver_bytes = stream_receiver.get("bytes", 0)
            receiver_bps = stream_receiver.get("bits_per_second", 0)
            retransmits = stream_sender.get("retransmits", 0)

        if sender_bytes == 0 and receiver_bytes == 0:
            return {
                "status": "failed",
                "sender_transfer_mb": 0,
                "sender_mbits_per_sec": 0,
                "sender_MB_per_sec": 0,
                "receiver_transfer_mb": 0,
                "receiver_mbits_per_sec": 0,
                "receiver_MB_per_sec": 0,
                "retransmits": 0,
                "error": "iperf3 returned zero traffic"
            }

        sender_transfer_mb = sender_bytes / 1024 / 1024
        receiver_transfer_mb = receiver_bytes / 1024 / 1024

        sender_mbits_per_sec = sender_bps / 1000 / 1000
        receiver_mbits_per_sec = receiver_bps / 1000 / 1000

        sender_MB_per_sec = sender_transfer_mb / TEST_DURATION
        receiver_MB_per_sec = receiver_transfer_mb / TEST_DURATION

        return {
            "status": "success",
            "sender_transfer_mb": sender_transfer_mb,
            "sender_mbits_per_sec": sender_mbits_per_sec,
            "sender_MB_per_sec": sender_MB_per_sec,
            "receiver_transfer_mb": receiver_transfer_mb,
            "receiver_mbits_per_sec": receiver_mbits_per_sec,
            "receiver_MB_per_sec": receiver_MB_per_sec,
            "retransmits": retransmits,
            "error": ""
        }

    except Exception as e:
        return {
            "status": "failed",
            "sender_transfer_mb": 0,
            "sender_mbits_per_sec": 0,
            "sender_MB_per_sec": 0,
            "receiver_transfer_mb": 0,
            "receiver_mbits_per_sec": 0,
            "receiver_MB_per_sec": 0,
            "retransmits": 0,
            "error": str(e)
        }


def write_csv(results):
    if not results:
        return

    with open(CSV_FILE, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "loop_number",
            "target_name",
            "target_ip",
            "target_port",
            "protocol",
            "duration_seconds",
            "sender_transfer_mb",
            "sender_mbits_per_second",
            "sender_MB_per_second",
            "receiver_transfer_mb",
            "receiver_mbits_per_second",
            "receiver_MB_per_second",
            "retransmits",
            "timestamp",
            "status",
            "error"
        ])

        for r in results:
            writer.writerow([
                r["loop_number"],
                r["target_name"],
                r["target_ip"],
                r["target_port"],
                r["protocol"],
                r["duration_seconds"],
                f"{r.get('sender_transfer_mb', 0):.2f}",
                f"{r.get('sender_mbits_per_sec', 0):.2f}",
                f"{r.get('sender_MB_per_sec', 0):.2f}",
                f"{r.get('receiver_transfer_mb', 0):.2f}",
                f"{r.get('receiver_mbits_per_sec', 0):.2f}",
                f"{r.get('receiver_MB_per_sec', 0):.2f}",
                r.get("retransmits", 0),
                r["timestamp"],
                r["status"],
                r.get("error", "")
            ])

        writer.writerow([])
        writer.writerow(["AVERAGES"])

        target_names = sorted(set(r["target_name"] for r in results))

        for name in target_names:
            successful = [
                r for r in results
                if r["target_name"] == name and r["status"] == "success"
            ]

            if not successful:
                continue

            avg_sender_mb = sum(r["sender_transfer_mb"] for r in successful) / len(successful)
            avg_sender_mbps = sum(r["sender_mbits_per_sec"] for r in successful) / len(successful)
            avg_sender_MBps = sum(r["sender_MB_per_sec"] for r in successful) / len(successful)

            avg_receiver_mb = sum(r["receiver_transfer_mb"] for r in successful) / len(successful)
            avg_receiver_mbps = sum(r["receiver_mbits_per_sec"] for r in successful) / len(successful)
            avg_receiver_MBps = sum(r["receiver_MB_per_sec"] for r in successful) / len(successful)

            avg_retransmits = sum(r["retransmits"] for r in successful) / len(successful)

            writer.writerow([
                name,
                "avg_sender_transfer_mb",
                f"{avg_sender_mb:.2f}",
                "avg_sender_mbits_per_second",
                f"{avg_sender_mbps:.2f}",
                "avg_sender_MB_per_second",
                f"{avg_sender_MBps:.2f}",
                "avg_receiver_transfer_mb",
                f"{avg_receiver_mb:.2f}",
                "avg_receiver_mbits_per_second",
                f"{avg_receiver_mbps:.2f}",
                "avg_receiver_MB_per_second",
                f"{avg_receiver_MBps:.2f}",
                "avg_retransmits",
                f"{avg_retransmits:.2f}"
            ])

    print(f"CSV saved: {CSV_FILE}")


def main():
    print("Starting iperf3 raw bandwidth benchmark")
    print(f"Protocol: {PROTOCOL}")
    print(f"Loops: {NUMBER_OF_LOOPS}")
    print(f"Duration per loop: {TEST_DURATION} seconds")

    try:
        for loop_number in range(1, NUMBER_OF_LOOPS + 1):
            print("\n==============================")
            print(f"Starting loop {loop_number}/{NUMBER_OF_LOOPS}")
            print("==============================")

            for target in IPERF_TARGETS:
                print(
                    f"Testing {target['name']} "
                    f"{target['ip']}:{target['port']}"
                )

                result = run_iperf_test(target)

                row = {
                    "loop_number": loop_number,
                    "target_name": target["name"],
                    "target_ip": target["ip"],
                    "target_port": target["port"],
                    "protocol": PROTOCOL,
                    "duration_seconds": TEST_DURATION,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    **result
                }

                all_results.append(row)

                if result["status"] == "success":
                    print(
                        f"Sender: {result['sender_transfer_mb']:.2f} MB, "
                        f"{result['sender_mbits_per_sec']:.2f} Mbits/sec, "
                        f"{result['sender_MB_per_sec']:.2f} MB/sec"
                    )
                    print(
                        f"Receiver: {result['receiver_transfer_mb']:.2f} MB, "
                        f"{result['receiver_mbits_per_sec']:.2f} Mbits/sec, "
                        f"{result['receiver_MB_per_sec']:.2f} MB/sec"
                    )
                    print(f"Retransmits: {result['retransmits']}")
                else:
                    print(f"Failed: {result['error']}")

                write_csv(all_results)
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        write_csv(all_results)

    finally:
        write_csv(all_results)
        print("iperf3 benchmark finished.")


if __name__ == "__main__":
    main()
