#!/usr/bin/env bash
# Start Hermes×Obsidian Phase-5 API on :8787
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8787
