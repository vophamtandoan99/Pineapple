#!/usr/bin/env bash
# Chạy cùng lúc backend (Python, :8765) và frontend (Vite, :5173)
# Ctrl+C dừng cả hai.
set -euo pipefail
cd "$(dirname "$0")"

# Dọn server cũ giữ port 8765: process chạy từ trong backend/ nên cmdline là
# "server.py" (pattern "backend/server.py" không khớp) — khớp cả 2 dạng.
pkill -f "reports/.*server\.py" 2>/dev/null || true
pkill -f "python3 server\.py" 2>/dev/null || true
sleep 0.5

(cd backend && exec python3 server.py) &
BE_PID=$!
(cd frontend && exec npm run dev) &
FE_PID=$!

trap 'kill $BE_PID $FE_PID 2>/dev/null; wait 2>/dev/null' EXIT INT TERM

# Đợi một trong hai tiến trình dừng lại
while kill -0 $BE_PID 2>/dev/null && kill -0 $FE_PID 2>/dev/null; do
    sleep 1
done
wait