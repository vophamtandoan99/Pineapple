# Image duy nhất: build frontend bằng Node, runtime gồm python backend + nginx
# trong cùng container. Entrypoint khởi động cả hai tiến trình.

# ---- Stage 1: build frontend ----
FROM node:20-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# nginx chạy cùng container để serve static + proxy /api/ về 127.0.0.1:8765
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default

WORKDIR /app/backend

# Cài dependencies trước để tận dụng layer cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/backend/

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
