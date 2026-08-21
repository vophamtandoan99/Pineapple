import os
import sys

# Thêm thư mục backend vào đường dẫn để python tìm thấy module
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from server import Handler
from http.server import HTTPServer

# Adapter để Vercel Serverless Function gọi đến Handler của bạn
class handler(Handler):
    def log_message(self, format, *args):
        pass  # Tắt log rườm rà trên serverless