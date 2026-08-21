# Deploy với Docker

Build một image duy nhất (`doanvpt/pineapple`) chứa cả frontend + backend,
chạy bằng Docker Compose.

## Cấu trúc

```
deploy/
├── Dockerfile          # 2 stage: Node build Vite -> python:3.12-slim + nginx
├── entrypoint.sh       # Khởi động backend + nginx trong cùng container
├── nginx.conf          # Serve SPA + proxy /api/ -> 127.0.0.1:8765
└── docker-compose.yml  # 1 service duy nhất
```

> Build context là thư mục gốc của repo (`..`), không phải `deploy/`. Các lệnh
> docker compose phải chạy từ trong `deploy/`.

## Yêu cầu

- Docker Engine 20.10+
- Docker Compose v2 (`docker compose`, không phải `docker-compose` cũ)

## Chạy

```bash
cd deploy
docker compose up -d --build
```

Kết quả: 1 container `reports-app` — mở http://localhost:7878.

Trong container: nginx nghe cổng 80 (serve UI + proxy), Python backend nghe
`127.0.0.1:8765`. Cả hai tiến trình do `entrypoint.sh` quản lý, dừng sạch khi
`docker stop`.

## Lệnh thường dùng

```bash
docker compose up -d --build   # Build + khởi động (nền)
docker compose ps              # Xem trạng thái container
docker compose logs -f         # Xem log trực tiếp (Ctrl+C để thoát)
docker compose restart         # Khởi động lại
docker compose down            # Dừng + xóa container (giữ image)
docker compose down --rmi all  # Dừng + xóa cả image
```

## Cấu hình

### Port

Đổi port ngoài trong `docker-compose.yml`:

```yaml
ports:
  - "7878:80"     # đổi "7878" thành port mong muốn, giữ "80"
```

### config.json

Backend lưu cài đặt (server TFS, org, user, token, rules) vào
`backend/config.json`. Compose bind mount file này từ máy host vào container,
nên:

- Cài đặt thay đổi từ UI được ghi thẳng ra file trên host — không mất khi
  rebuild/restart container.
- Muốn reset cài đặt: sửa/xóa file `backend/config.json` rồi restart.

File `config.json` chứa token TFS — không commit lên git (đã có trong
`.gitignore`).

### Biến môi trường

| Biến   | Mặc định    | Ý nghĩa                                     |
| ------ | ----------- | ------------------------------------------- |
| `HOST` | `127.0.0.1` | Địa chỉ bind của backend server — trong container nginx gọi qua `127.0.0.1` nên giữ mặc định |

Chạy local không Docker (dev): backend vẫn bind `127.0.0.1` như cũ, không ảnh
hưởng.

## Cách hoạt động

```
Browser --> nginx (:7878 -> :80 trong container)
             ├── static (dist/)          -- UI Vue đã build
             └── /api/  --proxy--> 127.0.0.1:8765 (python)  --http--> TFS Server
```

- **Dockerfile** gồm 2 stage: stage 1 dùng Node 20 chạy `npm install && npm
  run build`; stage 2 copy `dist/` sang image python:3.12-slim có cài nginx.
- **nginx.conf**: `try_files $uri $uri/ /index.html` cho SPA (route như
  `/dashboard` trả về `index.html`), `/api/` forward sang backend cùng
  container.
- **entrypoint.sh**: backend + nginx chạy background, PID 1 (`sh`) nhận
  SIGTERM từ `docker stop` và dọn cả hai tiến trình.
- **Dockerfile** copy `requirements.txt` và cài trước để tận dụng layer cache
  — sửa code backend không phải cài lại dependencies.

## Đẩy image lên Docker Hub

Xem [dockerhub-readme.md](dockerhub-readme.md).

## Sự cố thường gặp

| Hiện tượng                            | Nguyên nhân / cách xử lý                                        |
| ------------------------------------- | --------------------------------------------------------------- |
| `Cannot connect to the Docker daemon` | Docker Desktop chưa chạy — mở app Docker hoặc `open -a Docker` |
| Web mở được nhưng API lỗi 502         | Backend trong container chưa lên hoặc đã die — `docker compose logs` |
| Đổi code không thấy hiệu lực         | Thiếu `--build` — chạy lại `docker compose up -d --build`       |
| Port đã bị chiếm                      | Đổi port ngoài trong `docker-compose.yml` (cột trái)           |
