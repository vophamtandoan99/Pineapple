#!/bin/sh
# Khởi động backend + nginx, cả hai chạy background rồi wait —
# để sh (PID 1) nhận SIGTERM từ docker stop và dọn cả hai tiến trình.
# Backend nghe 127.0.0.1:8765, chỉ nginx trong container này gọi tới.
set -e

python /app/backend/server.py &
BACKEND_PID=$!

nginx -g 'daemon off;' &
NGINX_PID=$!

term_handler() {
    kill "$NGINX_PID" "$BACKEND_PID" 2>/dev/null || true
    exit 0
}
trap term_handler TERM INT

wait "$NGINX_PID"
