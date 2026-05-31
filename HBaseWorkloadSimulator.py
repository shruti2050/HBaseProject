import argparse
import time
import uuid
import random
import statistics
import sys
import json
from datetime import datetime, timezone

try:
    import happybase
except ImportError:
    print("[ERROR] happybase not found. Run: pip install happybase")
    sys.exit(1)

DEFAULT_HOST  = "localhost"
DEFAULT_PORT  = 9090
TABLE_NAME    = "zoho_analytics_logs"
COLUMN_FAMILY = "metrics"

EVENT_TYPES = ["page_view", "api_call", "login", "export", "report_gen", "dashboard_load"]
MODULES     = ["CRM", "Finance", "HR", "Analytics", "Marketing", "Support"]
REGIONS     = ["us-east-1", "us-west-2", "eu-central-1", "ap-south-1", "ap-southeast-1"]
STATUSES    = ["success", "failure", "timeout", "partial"]

def generate_row(seq_num):
    epoch = int(time.time() * 1000)
    reversed_epoch = 9_999_999_999_999 - epoch
    row_key = f"SEQ-{seq_num:05d}-{reversed_epoch}".encode()
    data = {
        f"{COLUMN_FAMILY}:event_type".encode():   random.choice(EVENT_TYPES).encode(),
        f"{COLUMN_FAMILY}:user_id".encode():      f"user_{random.randint(1000,9999)}".encode(),
        f"{COLUMN_FAMILY}:session_id".encode():   str(uuid.uuid4()).encode(),
        f"{COLUMN_FAMILY}:module".encode():        random.choice(MODULES).encode(),
        f"{COLUMN_FAMILY}:latency_ms".encode():   str(random.randint(10, 2500)).encode(),
        f"{COLUMN_FAMILY}:record_count".encode(): str(random.randint(1, 10000)).encode(),
        f"{COLUMN_FAMILY}:timestamp_iso".encode():datetime.now(timezone.utc).isoformat().encode(),
        f"{COLUMN_FAMILY}:region".encode():        random.choice(REGIONS).encode(),
        f"{COLUMN_FAMILY}:status".encode():        random.choice(STATUSES).encode(),
    }
    return row_key, data

def ensure_table(connection):
    tables = [t.decode() for t in connection.tables()]
    if TABLE_NAME not in tables:
        print(f"  [SETUP] Creating table '{TABLE_NAME}'...")
        connection.create_table(TABLE_NAME, {COLUMN_FAMILY: {"max_versions": 3}})
        print(f"  [SETUP] Table created successfully")
    else:
        print(f"  [SETUP] Table '{TABLE_NAME}' already exists")
    return connection.table(TABLE_NAME)

def run_write_benchmark(table, num_rows):
    print(f"\n--- WRITE BENCHMARK | {num_rows} rows ---")
    latencies  = []
    batch_size = 50
    written    = 0
    total_start = time.perf_counter()
    batch = table.batch(batch_size=batch_size)
    for seq in range(1, num_rows + 1):
        row_key, data = generate_row(seq)
        t0 = time.perf_counter()
        batch.put(row_key, data)
        if seq % batch_size == 0:
            batch.send()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)
        written += 1
        if seq % 50 == 0 or seq == num_rows:
            elapsed = time.perf_counter() - total_start
            rps = seq / elapsed if elapsed > 0 else 0
            print(f"  Progress: {seq}/{num_rows} | {rps:.1f} rows/sec", end="\r")
    batch.send()
    total_elapsed = time.perf_counter() - total_start
    throughput = written / total_elapsed if total_elapsed > 0 else 0
    print()
    return {
        "operation": "WRITE", "num_rows": written,
        "total_elapsed_s":   round(total_elapsed, 4),
        "throughput_rps":    round(throughput, 2),
        "latency_mean_ms":   round(statistics.mean(latencies), 4),
        "latency_median_ms": round(statistics.median(latencies), 4),
        "latency_p95_ms":    round(sorted(latencies)[int(len(latencies)*0.95)], 4),
        "latency_p99_ms":    round(sorted(latencies)[int(len(latencies)*0.99)], 4),
        "latency_min_ms":    round(min(latencies), 4),
        "latency_max_ms":    round(max(latencies), 4),
    }

def run_read_benchmark(table, num_rows):
    print(f"\n--- READ BENCHMARK | {num_rows} rows ---")
    latencies = []
    read = 0
    t0_total = time.perf_counter()
    for row_key, data in table.scan(limit=num_rows):
        t0 = time.perf_counter()
        _ = {k: v for k, v in data.items()}
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)
        read += 1
        if read % 50 == 0 or read == num_rows:
            elapsed = time.perf_counter() - t0_total
            rps = read / elapsed if elapsed > 0 else 0
            print(f"  Progress: {read}/{num_rows} | {rps:.1f} rows/sec", end="\r")
    total_elapsed = time.perf_counter() - t0_total
    throughput = read / total_elapsed if total_elapsed > 0 else 0
    print()
    return {
        "operation": "READ", "num_rows": read,
        "total_elapsed_s":   round(total_elapsed, 4),
        "throughput_rps":    round(throughput, 2),
        "latency_mean_ms":   round(statistics.mean(latencies), 4) if latencies else 0,
        "latency_median_ms": round(statistics.median(latencies), 4) if latencies else 0,
        "latency_p95_ms":    round(sorted(latencies)[int(len(latencies)*0.95)], 4) if latencies else 0,
        "latency_p99_ms":    round(sorted(latencies)[int(len(latencies)*0.99)], 4) if latencies else 0,
        "latency_min_ms":    round(min(latencies), 4) if latencies else 0,
        "latency_max_ms":    round(max(latencies), 4) if latencies else 0,
    }

def print_result(r):
    print(f"""
  +-----------------------------------------------+
  |  {r['operation']} RESULTS - {r['num_rows']} rows
  +-----------------------------------------------+
  |  Total time    : {r['total_elapsed_s']} s
  |  Throughput    : {r['throughput_rps']} rows/sec
  |  Latency mean  : {r['latency_mean_ms']} ms
  |  Latency median: {r['latency_median_ms']} ms
  |  Latency p95   : {r['latency_p95_ms']} ms
  |  Latency p99   : {r['latency_p99_ms']} ms
  |  Latency min   : {r['latency_min_ms']} ms
  |  Latency max   : {r['latency_max_ms']} ms
  +-----------------------------------------------+""")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",  default=DEFAULT_HOST)
    parser.add_argument("--port",  default=DEFAULT_PORT, type=int)
    parser.add_argument("--rows",  default=500, type=int)
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════╗
║   HBase Workload Simulator - Internship Project #7   ║
║   Table  : {TABLE_NAME:<40}║
║   Rows   : {args.rows:<40}║
║   Thrift : {args.host}:{args.port:<37}║
╚══════════════════════════════════════════════════════╝""")

    print(f"\n[1/4] Connecting to HBase Thrift at {args.host}:{args.port} ...")
    try:
        connection = happybase.Connection(host=args.host, port=args.port, timeout=15000)
        connection.open()
        print("      Connected")
    except Exception as e:
        print(f"\n[ERROR] Could not connect: {e}")
        print("  Make sure Thrift is running: docker exec -d hbase-master hbase thrift start")
        sys.exit(1)

    print("\n[2/4] Setting up table ...")
    try:
        table = ensure_table(connection)
    except Exception as e:
        print(f"[ERROR] Table setup failed: {e}")
        connection.close()
        sys.exit(1)

    print("\n[3/4] Running write benchmark ...")
    write_result = run_write_benchmark(table, args.rows)
    print_result(write_result)

    print("\n[4/4] Running read benchmark ...")
    read_result = run_read_benchmark(table, args.rows)
    print_result(read_result)

    fname = f"benchmark_{args.rows}rows_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump({"run_at": datetime.now().isoformat(), "results": [write_result, read_result]}, f, indent=2)
    print(f"\n  Results saved to: {fname}")
    print("\n  DONE\n")
    connection.close()

if __name__ == "__main__":
    main()
