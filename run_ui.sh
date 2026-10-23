#!/usr/bin/env bash
set -e

# Determine working directory
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Select Python binary
if [ -f "$DIR/venv/bin/python" ]; then
    PYTHON="$DIR/venv/bin/python"
elif [ -f "/home/aman/miniconda3/envs/innovions/bin/python" ]; then
    PYTHON="/home/aman/miniconda3/envs/innovions/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    PYTHON="python"
fi

PORT="${SEO_DASHBOARD_PORT:-8765}"
HOST="${SEO_DASHBOARD_HOST:-127.0.0.1}"

echo "=========================================================="
echo " Starting SEO & GEO Audit Suite UI..."
echo " Using Python: $PYTHON"
echo " Dashboard URL: http://${HOST}:${PORT}"
echo "=========================================================="

exec "$PYTHON" app.py
