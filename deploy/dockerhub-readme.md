# Đẩy image lên Docker Hub

Image duy nhất đã được đặt tên sẵn trong `docker-compose.yml`:
`doanvpt/pineapple:latest` (chứa cả frontend + backend).

## Bước 1: Build image với tên đúng

```bash
cd deploy
docker compose build

docker build -t doanvpt/pineapple:latest . # Build lại image mới với đúng tên và tag cũ
```

## Bước 2: Đăng nhập vào Docker Hub

```bash
docker login
```

(Nhập username doanvpt và mật khẩu của bạn khi được hỏi).

## Bước 3: Push image lên Docker Hub

```bash
docker push doanvpt/pineapple:latest
```

Sau khi lệnh chạy xong, image sẽ xuất hiện công khai (hoặc riêng tư tùy cài
đặt kho) tại: <https://hub.docker.com/r/doanvpt/pineapple>

## Tag version (tùy chọn)

Muốn giữ các phiên bản, tag thêm số version rồi push:

```bash
docker tag doanvpt/pineapple:latest doanvpt/pineapple:1.0.0
docker push doanvpt/pineapple:1.0.0
```

## Pull image về máy và chạy web

Trên máy mới (đã cài Docker), chỉ cần 1 image và 1 container:

```bash
# 1. Kéo image về máy
docker pull doanvpt/pineapple:latest

# 2. Chạy container, mở cổng 7878
docker run -d --name reports-app -p 7878:80 doanvpt/pineapple:latest
```

Mở http://localhost:7878 để dùng app.

Lưu ý:

- Backend trong container không mount `config.json` sẽ dùng cấu hình mặc định
  (`default.json`); cài đặt lưu từ UI chỉ tồn tại trong container — mất khi
  xóa container. Muốn giữ lại, tạo file `config.json` (nội dung `{}` là đủ)
  rồi mount khi chạy:

  ```bash
  docker run -d --name reports-app \
    -p 7878:80 \
    -v "$(pwd)/config.json:/app/backend/config.json" \
    doanvpt/pineapple:latest
  ```

- Muốn đổi cổng, sửa phần trước dấu `:` trong `-p 7878:80`.

Dừng và dọn dẹp:

```bash
docker stop reports-app
docker rm reports-app
```
