# Containerized HBase with Hadoop — Storage System
### SETU Project-Based Internship · Zoho Corporation · Project #7 · Batch 2027

A fully containerised Apache HBase storage system deployed via Docker Compose, benchmarked with a Python workload simulator, and verified with real analytics data.

---

## Results at a Glance

| Metric | Value |
|--------|-------|
| Total rows written | **1,600** (across 3 benchmark runs) |
| Peak write throughput | **938 rows/sec** (1000-row workload) |
| Peak read throughput | **18,467 rows/sec** (1000-row workload) |
| Read latency (mean) | **0.0007 ms** (sub-millisecond, MemStore cache) |
| Columns per row | **9** (in `metrics` column family) |
| Deployment command | `docker compose up -d` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              hbase-master container                         │
│              harisekhon/hbase:2.1                           │
│                                                             │
│  ┌─────────────────┐   ┌──────────────────────────────┐    │
│  │  ZooKeeper      │   │  HBase Master                │    │
│  │  port: 2181     │◄──┤  port: 16000                 │    │
│  │  (coordination) │   │  Web UI: 16010               │    │
│  └─────────────────┘   └──────────────────────────────┘    │
│                                        │                    │
│                         ┌──────────────▼───────────────┐   │
│                         │  RegionServer                 │   │
│                         │  port: 16020                  │   │
│                         │  MemStore → HFile on disk     │   │
│                         └──────────────────────────────┘   │
│                                        │                    │
│                         ┌──────────────▼───────────────┐   │
│                         │  Thrift Server                │   │
│                         │  port: 9090 ← Python connects │   │
│                         └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                                  ▲
                    happybase (Python 3, port 9090)
                                  │
                   HBaseWorkloadSimulator.py
```

**Data flow:** Python → happybase → Thrift `:9090` → RegionServer → MemStore (RAM) → HFile (disk) — coordinated by ZooKeeper.

---

## Tech Stack

| Component | Image / Tool | Version |
|-----------|-------------|---------|
| HBase + ZooKeeper + Thrift | `harisekhon/hbase` | 2.1 |
| Python client | `happybase` | 1.3.0 |
| Orchestration | Docker Compose | v2 |
| Host | Docker Desktop (WSL2) | — |

---

## Prerequisites

- Docker Desktop with at least **4 GB RAM** allocated
- Python 3.10+
- `pip install happybase`

---

## Project Structure

```
D:\HBaseProject\
├── docker-compose.yml            # 1-command cluster deployment
├── HBaseWorkloadSimulator.py     # Python benchmark & data loader
├── verify_storage.sh             # Storage proof script
├── README.md                     # This file
├── hbase-config\
│   └── hbase-site.xml            # HBase standalone config
└── benchmark_*.json              # Auto-saved benchmark results
```

---

## Quick Start

### Step 1 — Start the container
```bash
docker compose up -d
```

### Step 2 — Wait for HBase to initialize
```bash
timeout /t 90
```
> HBase takes ~60–90 seconds to fully initialize on first start.

### Step 3 — Verify it's ready
```bash
docker exec hbase-master tail -3 /hbase/logs/hbase--master-hbase-master.log
```
Look for: `Master has completed initialization`

### Step 4 — Run benchmarks
```bash
python HBaseWorkloadSimulator.py --rows 100
python HBaseWorkloadSimulator.py --rows 500
python HBaseWorkloadSimulator.py --rows 1000
```

### Step 5 — Open Web UI
```
http://localhost:16010
```

---

## Stopping the Cluster

```bash
# Stop containers (data preserved)
docker compose down

# Stop and wipe all data
docker compose down -v
```

---

## Benchmark Results

### Write Benchmark (batched puts, batch_size=50)

| Rows | Time (s) | Rows/sec | Mean Lat (ms) | Median (ms) | p95 (ms) | p99 (ms) |
|------|----------|----------|---------------|-------------|----------|----------|
| 100  | 0.4664   | 214.42   | 4.6202        | 0.0084      | 15.2103  | 249.39   |
| 500  | 0.7146   | 699.71   | 1.3965        | 0.0086      | 7.8241   | 14.96    |
| 1000 | 1.0658   | **938.26**   | 1.0355    | 0.0083      | 5.8268   | 7.55     |

### Read Benchmark (full table scan)

| Rows | Time (s) | Rows/sec | Mean Lat (ms) | Median (ms) | p95 (ms) | p99 (ms) |
|------|----------|----------|---------------|-------------|----------|----------|
| 100  | 0.1218   | 820.93   | 0.0009        | 0.0009      | 0.0013   | 0.0026   |
| 500  | 0.0001   | 6241.17  | 0.0013        | 0.0012      | 0.0014   | 0.0025   |
| 1000 | 0.0542   | **18467.19** | 0.0007    | 0.0006      | 0.0012   | 0.0014   |

### Key Observations

- **Write throughput scaled 4.4x** from 100→1000 rows. The JVM and Thrift connection pool warm up after the first batch, making subsequent writes significantly faster.
- **Read throughput is 20x higher than writes** because recently written data is served directly from HBase's in-memory MemStore — no disk I/O required.
- **p99 write latency dropped from 249ms → 7.5ms** as rows scaled up. The 249ms spike at 100 rows is a JVM cold-start artefact, not a structural bottleneck.

---

## Data Schema

**Table:** `zoho_analytics_logs`
**Column Family:** `metrics`
**Max versions:** 3

| Column | Example Value | Description |
|--------|--------------|-------------|
| `metrics:event_type` | `login` | Event type: page_view, api_call, login, export... |
| `metrics:user_id` | `user_4821` | User who triggered the event |
| `metrics:session_id` | `23e66845-beeb-...` | Unique UUID per session |
| `metrics:module` | `Finance` | Zoho module: CRM, HR, Analytics, Marketing... |
| `metrics:latency_ms` | `815` | Simulated response latency in ms |
| `metrics:record_count` | `3200` | Records in the event payload |
| `metrics:timestamp_iso` | `2026-05-28T08:35:52Z` | UTC event timestamp (ISO 8601) |
| `metrics:region` | `us-east-1` | Deployment region of event source |
| `metrics:status` | `timeout` | Outcome: success / failure / timeout / partial |

---

## Row Key Design

**Format:** `SEQ-{seq_num:05d}-{reversed_epoch}`

```python
reversed_epoch = 9_999_999_999_999 - int(time.time() * 1000)
row_key = f"SEQ-{seq_num:05d}-{reversed_epoch}"
```

HBase stores rows in **lexicographic key order**. By using a reversed epoch timestamp, the most recent events always sort to the top of the table. A `SCAN` with `LIMIT=N` returns the N most recent events without any secondary index or post-processing.

---

## Verify Storage

```bash
bash verify_storage.sh
```

Or manually via HBase shell:

```bash
docker exec -it hbase-master hbase shell

# Inside shell:
list
count 'zoho_analytics_logs'                  # → 1600 rows
scan 'zoho_analytics_logs', {LIMIT => 3}     # Preview rows
describe 'zoho_analytics_logs'               # Show schema
exit
```

---

## Ports Reference

| Port | Service | Used by |
|------|---------|---------|
| `9090` | Thrift API | Python happybase client |
| `16010` | HBase Master Web UI | Browser — `http://localhost:16010` |
| `2181` | ZooKeeper | Internal cluster coordination |
| `16000` | HBase Master RPC | Internal — master ↔ regionserver |
| `16020` | RegionServer RPC | Internal — data reads/writes |
| `9095` | Thrift2 API | Not used in this project |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ConnectionRefusedError` on port 9090 | Wait 90 seconds after `docker compose up -d` |
| `timed out` on table setup | Wait 30 more seconds and retry |
| Container not starting | Docker Desktop must be running with ≥4 GB RAM |
| Port already in use | Run `docker rm -f hbase-master` then `docker compose up -d` |
| `localhost:16010` not loading | Run `docker logs hbase-master --tail 10` to check status |

---

## References

- [Apache HBase Documentation](https://hbase.apache.org/)
- [HBase Architecture Guide](https://hbase.apache.org/book.html)
- [happybase Python Library](https://happybase.readthedocs.io/)
- [HDFS Design](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)

---

*SETU Project-Zoho Corporation · Project #7 · Batch 2027*