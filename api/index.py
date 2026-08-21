"""Vercel serverless entry: nạp Handler từ backend/server.py.

Vercel bundle chứa cả project (cwd = project root), nên chỉ cần thêm
backend/ vào sys.path. vercel.json rewrite mọi /api/* về đây.
Lưu ý: KHÔNG để fastapi/flask trong requirements.txt — Vercel sẽ bật
framework preset và bỏ qua các function trong /api.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from server import Handler  # noqa: E402


class handler(Handler):
    def log_message(self, format, *args):
        pass  # tắt log rườm rà trên serverless
