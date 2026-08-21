#!/usr/bin/env bash
# Chạy cùng lúc backend (Python, :8765) và frontend (Vite, :5173)
# Ctrl+C dừng cả hai.
set -euo pipefail
cd "$(dirname "$0")"

pkill -f "backend/server.py" 2>/dev/null || true
sleep 0.3

(cd backend && exec python3 server.py) &
BE_PID=$!
(cd frontend && exec npm run dev) &
FE_PID=$!

trap 'kill $BE_PID $FE_PID 2>/dev/null; wait 2>/dev/null' EXIT INT TERM
wait -n
