import subprocess
import time
import signal
import sys


IPERF_PORTS = [
    5201,
    # 5202,
    # 5203,
]


processes = []


def start_iperf_server(port):
    print(f"Starting iperf3 server on port {port}")
    p = subprocess.Popen(
        ["iperf3", "-s", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return p


def stop_servers():
    print("\nStopping iperf3 servers...")
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass


def main():
    global processes

    for port in IPERF_PORTS:
        processes.append(start_iperf_server(port))

    print("iperf3 receiver is running.")
    print("Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        stop_servers()

    finally:
        stop_servers()


if __name__ == "__main__":
    main()
