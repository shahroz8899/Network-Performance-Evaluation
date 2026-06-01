import subprocess
import json
import csv
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


IPERF_TARGETS = [
    {
        "ip": "192.168.1.##",
        "port": 5201,
        "name": "##"
    },
    {
        "ip": "192.168.1.###",
        "port": 5202,
        "name": "##"
    },

    # {
    #     "ip": "###.###.###.###",
    #     "port": 5203,
    #     "name": "##"
    # },
]


TEST_DURATION = 10
NUMBER_OF_LOOPS = 50
PROTOCOL = "tcp"

CSV_FILE = "iperf3_parallel_results.csv"

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

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TEST_DURATION + 20
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

        if sender_bytes == 0 and "streams" in end_data and len(end_data["streams"]) > 0:
            stream_sender = end_data["streams"][0].get("sender", {})
            stream_receiver = end_data["streams"][0].get("receiver", {})

            sender_bytes = stream_sender.get("bytes", 0)
            sender_bps = stream_sender.get("bits_per_second", 0)
            receiver_bytes = stream_receiver.get("bytes", 0)
            receiver_bps = stream_receiver.get("bits_per_second", 0)
            retransmits = stream_sender.get("retransmits", 0)

        sender_transfer_mb = sender_bytes / 1024 / 1024
        receiver_transfer_mb = receiver_bytes / 1024 / 1024

        sender_mbits_per_sec = sender_bps / 1000 / 1000
        receiver_mbits_per_sec = receiver_bps / 1000 / 1000

        sender_MB_per_sec = sender_transfer_mb / TEST_DURATION
        receiver_MB_per_sec = receiver_transfer_mb / TEST_DURATION

        if sender_bytes == 0 and receiver_bytes == 0:
            status = "failed"
            error = "iperf3 returned zero traffic"
        else:
            status = "success"
            error = ""

        return {
            "status": status,
            "sender_transfer_mb": sender_transfer_mb,
            "sender_mbits_per_sec": sender_mbits_per_sec,
            "sender_MB_per_sec": sender_MB_per_sec,
            "receiver_transfer_mb": receiver_transfer_mb,
            "receiver_mbits_per_sec": receiver_mbits_per_sec,
            "receiver_MB_per_sec": receiver_MB_per_sec,
            "retransmits": retransmits,
            "error": error
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
                f"{r["sender_transfer_mb"]:.2f}",
                f"{r["sender_mbits_per_sec"]:.2f}",
                f"{r["sender_MB_per_sec"]:.2f}",
                f"{r["receiver_transfer_mb"]:.2f}",
                f"{r["receiver_mbits_per_sec"]:.2f}",
                f"{r["receiver_MB_per_sec"]:.2f}",
                r["retransmits"],
                r["timestamp"],
                r["status"],
                r["error"]
            ])

    print(f"CSV saved: {CSV_FILE}")


def make_collective_row(loop_number, loop_results):
    successful = [r for r in loop_results if r["status"] == "success"]

    return {
        "loop_number": loop_number,
        "target_name": "COLLECTIVE_TOTAL",
        "target_ip": "multiple",
        "target_port": "multiple",
        "protocol": PROTOCOL,
        "duration_seconds": TEST_DURATION,
        "sender_transfer_mb": sum(r["sender_transfer_mb"] for r in successful),
        "sender_mbits_per_sec": sum(r["sender_mbits_per_sec"] for r in successful),
        "sender_MB_per_sec": sum(r["sender_MB_per_sec"] for r in successful),
        "receiver_transfer_mb": sum(r["receiver_transfer_mb"] for r in successful),
        "receiver_mbits_per_sec": sum(r["receiver_mbits_per_sec"] for r in successful),
        "receiver_MB_per_sec": sum(r["receiver_MB_per_sec"] for r in successful),
        "retransmits": sum(r["retransmits"] for r in successful),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "success" if successful else "failed",
        "error": ""
    }


def main():
    print("Starting parallel iperf3 raw bandwidth benchmark")
    print(f"Protocol: {PROTOCOL}")
    print(f"Loops: {NUMBER_OF_LOOPS}")
    print(f"Duration per loop: {TEST_DURATION} seconds")
    print(f"Parallel targets: {len(IPERF_TARGETS)}")

    for loop_number in range(1, NUMBER_OF_LOOPS + 1):
        print("\n==============================")
        print(f"Starting loop {loop_number}/{NUMBER_OF_LOOPS}")
        print("==============================")

        loop_results = []

        with ThreadPoolExecutor(max_workers=len(IPERF_TARGETS)) as executor:
            future_to_target = {
                executor.submit(run_iperf_test, target): target
                for target in IPERF_TARGETS
            }

            for future in as_completed(future_to_target):
                target = future_to_target[future]
                result = future.result()

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

                loop_results.append(row)

                if result["status"] == "success":
                    print(
                        f"{target['name']} receiver: "
                        f"{result['receiver_transfer_mb']:.2f} MB, "
                        f"{result['receiver_mbits_per_sec']:.2f} Mbits/sec, "
                        f"{result['receiver_MB_per_sec']:.2f} MB/sec"
                    )
                else:
                    print(f"{target['name']} failed: {result['error']}")

        collective = make_collective_row(loop_number, loop_results)
        loop_results.append(collective)

        print("\nCollective total:")
        print(
            f"Sender total: {collective['sender_transfer_mb']:.2f} MB, "
            f"{collective['sender_mbits_per_sec']:.2f} Mbits/sec, "
            f"{collective['sender_MB_per_sec']:.2f} MB/sec"
        )
        print(
            f"Receiver total: {collective['receiver_transfer_mb']:.2f} MB, "
            f"{collective['receiver_mbits_per_sec']:.2f} Mbits/sec, "
            f"{collective['receiver_MB_per_sec']:.2f} MB/sec"
        )
        print(f"Total retransmits: {collective['retransmits']}")

        all_results.extend(loop_results)
        write_csv(all_results)

        time.sleep(1)

    print("iperf3 parallel benchmark finished.")


if __name__ == "__main__":
    main()
