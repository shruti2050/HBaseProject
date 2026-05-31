#!/bin/bash
# ============================================================
# Storage Verification Script — Project #7
# Run this after your benchmarks to prove data persistence
# Usage: bash verify_storage.sh
# ============================================================

echo ""
echo "=== HBase Storage Verification ==="
echo ""

echo "--- 1. Container status ---"
docker compose ps
echo ""

echo "--- 2. HBase data directory on local filesystem ---"
docker exec hbase-master find /tmp/hbase-root -type f -name "*.hfile" 2>/dev/null | head -20
echo ""

echo "--- 3. HBase root directory listing ---"
docker exec hbase-master ls -la /tmp/hbase-root/ 2>/dev/null || \
docker exec hbase-master ls -la /tmp/ 2>/dev/null
echo ""

echo "--- 4. Row count via HBase shell ---"
docker exec hbase-master hbase shell << 'HBASE'
count 'zoho_analytics_logs'
exit
HBASE
echo ""

echo "--- 5. Sample rows ---"
docker exec hbase-master hbase shell << 'HBASE'
scan 'zoho_analytics_logs', {LIMIT => 3}
exit
HBASE

echo ""
echo "=== Verification complete ==="