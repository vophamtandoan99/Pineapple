# TFS Report

Công cụ tạo báo cáo công việc hàng ngày từ TFS (Azure DevOps Server).

Gồm 2 phần:

```
frontend/   # Vue 3 + PrimeVue — UI: login, dashboard, chọn item, tạo report
backend/    # Python stdlib — API server (port 8765) + CLI
```

## Chạy

Terminal 1 — backend:

```bash
python3 backend/server.py        # http://127.0.0.1:8765
python3 backend/server.py 9000   # port khác
```

Terminal 2 — frontend:

```bash
cd frontend
npm install
npm run dev                      # Vite proxy /api -> 127.0.0.1:8765
```

## Cấu hình

`backend/config.json` — tự tạo bằng CLI `run report init` (hoặc `python3 backend/tfs_report.py init`), gồm: fullname, server URL, user/pass. File chứa mật khẩu plaintext, đã chmod `600` — chỉ giữ trên máy cá nhân.

## Sử dụng

Trình duyệt mở frontend:

1. **Login** — tài khoản TFS, session lưu in-memory, không persist
2. **Dashboard** — thống kê item theo sprint hiện tại (Type, State, tiến độ)
3. **Report** — chọn item "Mới" / "Cũ", chọn ngày, "Tạo report" — preview + ghi file
4. **Đổi dự án** — chuyển collection/project trên topbar

File report ghi vào `<cwd>/<yyyy>/<m>/<d>.md`.

Định dạng report theo template trong `frontend/public/templetes/`:
phần **chat** (báo cáo nhân sự: công việc hôm nay / ngày tiếp theo / vấn đề) và phần **lark** (bảng Task ID, Task Name, Task Link, Type).

## CLI (tùy chọn)

```bash
python3 backend/tfs_report.py init   # thiết lập config
python3 backend/tfs_report.py        # tạo report bằng terminal
```

Chi tiết: xem docstring đầu file `backend/tfs_report.py`.

## Build frontend

```bash
cd frontend && npm run build   # xuất ra frontend/dist
```
