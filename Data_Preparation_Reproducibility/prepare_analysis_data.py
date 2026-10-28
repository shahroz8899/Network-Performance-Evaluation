#!/usr/bin/env python3
import argparse
import csv
import json
import re
import tempfile
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

TECH_ORDER = {"CoAP": 0, "HTTP": 1, "Kafka": 2, "MQTT": 3, "Zenoh": 4, "iPerf3": 5}
NET_ORDER = {"LAN": 0, "Wi-Fi": 1}
CASE_INFO = {
    1: ("One -> One", 1, 1, "single_sender_single_receiver", "single_pipeline"),
    2: ("One -> Two", 1, 2, "single_sender_multi_receiver", "fanout"),
    3: ("One -> Three", 1, 3, "single_sender_multi_receiver", "fanout"),
    4: ("Two -> One", 2, 1, "multi_sender_single_receiver", "receiver_contention"),
    5: ("Two -> Two", 2, 2, "multi_sender_multi_receiver", "parallel_pipelines"),
    6: ("Three -> One", 3, 1, "multi_sender_single_receiver", "receiver_contention"),
    7: ("Three -> Three", 3, 3, "multi_sender_multi_receiver", "many_to_many"),
}


def num(value):
    return Decimal(value) if value not in (None, "") else None


def run_number(value, strict=False):
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    if strict and d != d.to_integral_value():
        return None
    run = int(d)
    return run if 1 <= run <= 50 else None


def show(value):
    if value is None:
        return ""
    s = format(value, "f") if isinstance(value, Decimal) else str(value)
    return s.rstrip("0").rstrip(".") if "." in s else s


def classify(path):
    text = "/" + "/".join(path.parts).lower() + "/"
    names = (("/coap/", "CoAP"), ("/http/", "HTTP"), ("/kafka/", "Kafka"),
             ("/mqtt/", "MQTT"), ("/zenoh/", "Zenoh"))
    tech = next((name for marker, name in names if marker in text), None)
    if tech is None and ("/ipref 3/" in text or "/iperf3/" in text):
        tech = "iPerf3"
    if tech is None:
        return None

    parts = [p.lower() for p in path.parts]
    network = "LAN" if "lan" in parts else "Wi-Fi" if any("wifi" in p for p in parts) else None
    match = re.search(r"case[_ ]*([0-9])", path.name, re.I)
    return (tech, network, int(match.group(1))) if network and match else None


def node_name(path):
    for part in path.parts:
        p = part.lower()
        if p == "agx":
            return "AGX"
        if p == "nuc":
            return "NUC"
        if p in ("orin", "orin1"):
            return "ORIN"
    return ""


def sender_name(path):
    match = re.search(r"sent from (pi\d)", str(path), re.I)
    return "Pi" + match.group(1)[2:] if match else ""


def csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def individual_rows(root):
    output = []
    for path in sorted(root.rglob("*.csv")):
        info = classify(path)
        if not info:
            continue
        tech, network, case_num = info
        rel = path.relative_to(root)
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for source_row, row in enumerate(reader, 2):
                run = run_number(row.get("loop_number"), strict=True)
                if run is None:
                    continue
                if tech == "iPerf3" and row.get("target_name") == "COLLECTIVE_TOTAL":
                    continue

                if tech == "iPerf3":
                    values = {
                        "Node": row.get("target_name", ""), "Sender": sender_name(path),
                        "Throughput_Source_MBps": num(row.get("receiver_MB_per_second")),
                        "Duration_s": num(row.get("duration_seconds")), "Images_Total": None,
                        "Transfer_Source_MB": num(row.get("receiver_transfer_mb")), "Images_Per_Second": None,
                        "Status": row.get("status", ""), "Sender_Source_MBps": num(row.get("sender_MB_per_second")),
                        "Receiver_Reported_Mbps": num(row.get("receiver_mbits_per_second")),
                        "Source_Rate_Field": "receiver_MB_per_second"
                    }
                else:
                    values = {
                        "Node": node_name(path), "Sender": "", "Throughput_Source_MBps": num(row.get("mb_per_second")),
                        "Duration_s": num(row.get("run_duration_seconds")), "Images_Total": num(row.get("total_images")),
                        "Transfer_Source_MB": num(row.get("total_size_mb")), "Images_Per_Second": num(row.get("images_per_second")),
                        "Status": row.get("status", ""), "Sender_Source_MBps": None,
                        "Receiver_Reported_Mbps": None, "Source_Rate_Field": "mb_per_second"
                    }

                output.append({
                    "Network": network, "Technology": tech, "Case": f"Case{case_num}", "Run": run,
                    "Timestamp": row.get("timestamp", ""), "Source_File": str(rel).replace("\\", "/"),
                    "Source_Row": source_row, "Raw_Row_JSON": json.dumps(row, separators=(",", ":")), **values
                })

    output.sort(key=lambda r: (NET_ORDER[r["Network"]], TECH_ORDER[r["Technology"]], int(r["Case"][4:]), r["Run"], r["Source_File"], r["Source_Row"]))
    return output


def analysis_components(root):
    output = []
    for path in sorted(root.rglob("*.csv")):
        info = classify(path)
        if not info:
            continue
        tech, network, case_num = info
        rel = str(path.relative_to(root)).replace("\\", "/")
        rows = list(csv_rows(path))

        if tech == "iPerf3":
            by_run = defaultdict(list)
            for row in rows:
                run = run_number(row.get("loop_number"), strict=True)
                if run is not None:
                    by_run[run].append(row)
            for run, items in by_run.items():
                selected = [x for x in items if x.get("target_name") == "COLLECTIVE_TOTAL"]
                if not selected:
                    selected = [x for x in items if x.get("target_name") != "COLLECTIVE_TOTAL"]
                output.append({
                    "Network": network, "Technology": tech, "Case": f"Case{case_num}", "Run": run,
                    "Throughput": sum((num(x.get("receiver_MB_per_second")) or Decimal(0)) for x in selected),
                    "Mbps": sum((num(x.get("receiver_mbits_per_second")) or Decimal(0)) for x in selected),
                    "Images": None, "IPS": None, "Transfer": None,
                    "Duration": next((num(x.get("duration_seconds")) for x in reversed(selected) if num(x.get("duration_seconds")) is not None), None),
                    "Source_File": rel
                })
            continue

        for row in rows:
            run = run_number(row.get("loop_number"), strict=False)
            if run is None:
                continue
            failed = row.get("status") == "no_images_received"
            output.append({
                "Network": network, "Technology": tech, "Case": f"Case{case_num}", "Run": run,
                "Throughput": num(row.get("mb_per_second")), "Mbps": None,
                "Images": None if failed or num(row.get("total_images")) is None else Decimal(int(num(row.get("total_images")))),
                "IPS": None if failed else num(row.get("images_per_second")),
                "Transfer": None if failed else num(row.get("total_size_mb")),
                "Duration": num(row.get("run_duration_seconds")), "Source_File": rel
            })
    return output


def sum_present(items, field):
    values = [x[field] for x in items if x[field] is not None]
    return sum(values, Decimal(0)) if values else None


def aggregate(components):
    groups = defaultdict(list)
    for row in components:
        groups[(row["Network"], row["Technology"], row["Case"], row["Run"])].append(row)

    output = []
    for (network, tech, case, run), items in groups.items():
        case_num = int(case[4:])
        topology, senders, receivers, pattern, arch = CASE_INFO[case_num]
        throughput = sum_present(items, "Throughput") or Decimal(0)
        mbps = sum_present(items, "Mbps") if tech == "iPerf3" else throughput * Decimal(8)
        images = sum_present(items, "Images")
        if images is not None:
            images = Decimal(int(images))
        duration = next((x["Duration"] for x in reversed(items) if x["Duration"] is not None), None)

        output.append({
            "Network": network, "Technology": tech, "Layer": "Network baseline" if tech == "iPerf3" else "Middleware",
            "Case": case, "Case_Number": case_num, "Topology": topology, "Run": run,
            "Sender_Count": senders, "Receiver_Count": receivers, "Communication_Pattern": pattern,
            "Architecture_Class": arch, "Collective_Throughput_MBps": throughput,
            "Collective_Throughput_Mbps": mbps, "Collective_Images_Total": images,
            "Collective_Images_Per_Second": sum_present(items, "IPS"),
            "Collective_Transfer_MB": sum_present(items, "Transfer"), "Duration_s": duration,
            "Components_Summed": len(items), "Source_File_Count": len({x["Source_File"] for x in items})
        })

    output.sort(key=lambda r: (NET_ORDER[r["Network"]], TECH_ORDER[r["Technology"]], r["Case_Number"], r["Run"]))
    return output


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: show(row.get(key)) for key in fields})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--out", default="output")
    args = parser.parse_args()

    source = Path(args.input).resolve()
    outdir = Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    temp = None
    if source.is_file():
        temp = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(source) as archive:
            archive.extractall(temp.name)
        root = Path(temp.name)
    else:
        root = source

    children = [p for p in root.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        root = children[0]

    raw = individual_rows(root)
    analysis = aggregate(analysis_components(root))

    raw_fields = ["Network", "Technology", "Case", "Node", "Sender", "Run", "Throughput_Source_MBps", "Duration_s",
                  "Images_Total", "Transfer_Source_MB", "Images_Per_Second", "Timestamp", "Status", "Sender_Source_MBps",
                  "Receiver_Reported_Mbps", "Source_File", "Source_Row", "Source_Rate_Field", "Raw_Row_JSON"]
    analysis_fields = ["Network", "Technology", "Layer", "Case", "Case_Number", "Topology", "Run", "Sender_Count",
                       "Receiver_Count", "Communication_Pattern", "Architecture_Class", "Collective_Throughput_MBps",
                       "Collective_Throughput_Mbps", "Collective_Images_Total", "Collective_Images_Per_Second",
                       "Collective_Transfer_MB", "Duration_s", "Components_Summed", "Source_File_Count"]

    write_csv(outdir / "Master_Dataset_8100.csv", raw, raw_fields)
    write_csv(outdir / "Analysis_Dataset_4200.csv", analysis, analysis_fields)

    if len(raw) != 8100 or len(analysis) != 4200:
        raise SystemExit(f"Unexpected row counts: {len(raw)} and {len(analysis)}")
    print("8100 individual records")
    print("4200 analysis observations")


if __name__ == "__main__":
    main()
