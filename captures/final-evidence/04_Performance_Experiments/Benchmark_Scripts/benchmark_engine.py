import sys
import subprocess
import time
import json
import csv
import statistics
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
source = sys.argv[2]
label = sys.argv[3]
condition = sys.argv[4]
added_rtt = int(sys.argv[5])

count = 1000

def run(service, *args):
    return subprocess.check_output(
        ["./run-cn12.sh", "exec", "-T", service, *args],
        text=True
    )

def check_queues():
    for attempt in range(60):
        queues = [
            run(service, "postqueue", "-p")
            for service in ("mail-alpha", "mail-beta")
        ]

        if all("Mail queue is empty" in q for q in queues):
            print("PASS: Both mail queues empty", flush=True)
            return

        time.sleep(2)

    raise RuntimeError("Mail queues did not become empty")

scan_code = r'''
import sys
import json
import re
from pathlib import Path
from email import policy
from email.parser import BytesHeaderParser
from email.utils import parsedate_to_datetime

tag = sys.argv[1]
root = Path("/home/adil/Maildir")
results = []

for folder in ("new", "cur"):
    for path in (root / folder).glob("*"):
        if not path.is_file():
            continue

        try:
            with path.open("rb") as file:
                msg = BytesHeaderParser(
                    policy=policy.default
                ).parse(file)

            modified = path.stat().st_mtime

        except FileNotFoundError:
            continue

        if str(msg.get("Subject", "")) != tag:
            continue

        spf = any(
            re.match(r"^\s*pass\b", str(h), re.I)
            and "10.10.1.10" in str(h)
            for h in msg.get_all("Received-SPF", [])
        )

        dkim = any(
            str(h).strip().lower().startswith("mail.beta.lab;")
            and re.search(r"\bdkim=pass\b", str(h), re.I)
            for h in msg.get_all("Authentication-Results", [])
        )

        alpha_time = None

        for header in msg.get_all("Received", []):
            header = str(header)

            if re.search(r"\bby\s+mail\.alpha\.lab\b", header, re.I):
                try:
                    alpha_time = parsedate_to_datetime(
                        header.rsplit(";", 1)[-1].strip()
                    ).timestamp()
                except (ValueError, TypeError):
                    pass
                break

        latency = None

        if alpha_time is not None and modified >= alpha_time:
            latency = round((modified - alpha_time) * 1000, 3)

        results.append({
            "maildir_file": path.name,
            "message_id": str(msg.get("Message-ID", "")),
            "spf_pass": spf,
            "dkim_pass": dkim,
            "alpha_received_epoch": alpha_time,
            "maildir_mtime_epoch": modified,
            "estimated_latency_ms": latency
        })

print(json.dumps(results))
'''

print("===== CHECKING INITIAL MAIL QUEUES =====", flush=True)

check_queues()

tag = f"CN12-{label}-{time.time_ns()}"

started = datetime.now(timezone.utc).isoformat()

print("Run identifier:", tag, flush=True)

print(f"===== SENDING {count} EMAILS =====", flush=True)

start = time.monotonic()

subprocess.run(
    [
        "./run-cn12.sh", "exec", "-T",
        "mail-alpha", source,
        "-m", str(count),
        "-s", "10",
        "-l", "1024",
        "-f", "zaid@alpha.lab",
        "-t", "adil@beta.lab",
        "-S", tag,
        "127.0.0.1:25"
    ],
    check=True,
    timeout=600
)

submission_time = time.monotonic() - start

print("SMTP submission completed", flush=True)
print(f"Submission time: {submission_time:.3f} s", flush=True)

deadline = time.monotonic() + 600
previous = -1

while True:
    messages = json.loads(
        run("mail-beta", "python3", "-c", scan_code, tag)
    )

    delivered = len(messages)

    if delivered != previous:
        print(f"Delivered: {delivered}/{count}", flush=True)
        previous = delivered

    if delivered >= count:
        break

    if time.monotonic() >= deadline:
        print("FAIL: Delivery observation timeout", flush=True)
        break

    time.sleep(1)

delivery_time = time.monotonic() - start

spf_pass = sum(m["spf_pass"] for m in messages)
dkim_pass = sum(m["dkim_pass"] for m in messages)

latencies = [
    m["estimated_latency_ms"]
    for m in messages
    if m["estimated_latency_ms"] is not None
]

metrics = {
    "experiment": label,
    "network_condition": condition,
    "added_rtt_ms": added_rtt,
    "started_utc": started,
    "subject": tag,
    "messages_requested": count,
    "messages_delivered": delivered,
    "delivery_success_percent": delivered / count * 100,
    "parallel_sessions": 10,
    "payload_bytes": 1024,
    "submission_seconds": submission_time,
    "submission_messages_per_second": count / submission_time,
    "observed_delivery_seconds": delivery_time,
    "observed_delivery_messages_per_second": delivered / delivery_time,
    "spf_pass": spf_pass,
    "dkim_pass": dkim_pass,
    "spf_pass_percent": spf_pass / delivered * 100 if delivered else None,
    "dkim_pass_percent": dkim_pass / delivered * 100 if delivered else None,
    "latency_samples": len(latencies),
    "estimated_mean_latency_ms": statistics.mean(latencies) if latencies else None,
    "estimated_latency_stddev_ms": statistics.stdev(latencies) if len(latencies) > 1 else None
}

fields = [
    "maildir_file",
    "message_id",
    "spf_pass",
    "dkim_pass",
    "alpha_received_epoch",
    "maildir_mtime_epoch",
    "estimated_latency_ms"
]

with (out / f"{label}_Messages.csv").open("w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(messages)

with (out / f"{label}_Metrics.json").open("w") as file:
    json.dump(metrics, file, indent=2)

with (out / f"{label}_Metrics.csv").open("w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(metrics))
    writer.writeheader()
    writer.writerow(metrics)

print("\n===== BENCHMARK RESULTS =====")

for key, value in metrics.items():
    print(f"{key}: {value}")

if delivered != count:
    raise RuntimeError("Email delivery count mismatch")

if spf_pass != count or dkim_pass != count:
    raise RuntimeError("Email authentication mismatch")

print(f"PASS: All {count} emails delivered")
print("PASS: SPF verification")
print("PASS: DKIM verification")

check_queues()

print("ALL BENCHMARK CHECKS COMPLETED")
