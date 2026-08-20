# Hướng dẫn sử dụng `tfs_report.py`

Công cụ lấy work items từ TFS (Azure DevOps Server) và tạo báo cáo hàng ngày.

## Web UI (tùy chọn)

```bash
run web          # http://127.0.0.1:8765
run web 9000     # port khác
```

Trình duyệt: đăng nhập → bảng thống kê Type/State → danh sách item (search, filter State, checkbox chọn, "Chọn tất cả") → chọn ngày → "Tạo report" → xem preview + đường dẫn file. Nút "Đăng xuất" xóa session.

## Yêu cầu

- Python 3 (chuẩn, không cần cài thêm package)
- `curl` (có sẵn trên Linux)

## Cách chạy

### Thiết lập ban đầu (chỉ làm 1 lần)

```bash
run report init
```

Hỏi tuần tự:
- Họ tên đầy đủ (hiển thị trong báo cáo)
- TFS server (mặc định `https://tfs.tmtco.dev`)
- Collection/Org (mặc định `TMTAICollection`)
- Project (mặc định `Team_AI`)
- Username
- Có lưu mật khẩu vào config không? `[y/N]` — nếu `y` thì hỏi mật khẩu, lưu plaintext

Lưu vào `~/Documents/Report/config.json`, phân quyền `600`.

### Logout

```bash
run report logout
```

Xóa mật khẩu đã lưu khỏi `config.json` và `TFS_PASS` khỏi env. Lần chạy sau sẽ hỏi mật khẩu lại.

### Chạy hàng ngày

```bash
run report
```

- Có mật khẩu lưu → chạy thẳng, không hỏi
- Không lưu → hỏi password (ẩn)

### Quy trình khi chạy

1. **Đăng nhập** — `Login OK: <username>`
2. **Chọn kiểu report** — menu mũi tên:
   ```
   Chọn kiểu report:
   ❯ Report hôm nay
     Report ngày cũ
   ```
   - `↑/↓` di chuyển, `Enter` chọn, `1/2` chọn nhanh

3. **Xác nhận file** — `Report sẽ ghi vào: 2026/8/20.md (file đã có — sẽ update)` hoặc `(tạo mới)`
4. **Thống kê work items** — 2 bảng có viền (không hiện 148 dòng):
   ```
   Work items của bạn: 148

   | Type           | Count |
   |----------------|------:|
   | Bug            |    53 |
   | Task           |    77 |
   | User Story     |    18 |

   | State         | Count |
   |---------------|------:|
   | Active          |     6 |
   | Closed          |   121 |
   | New             |    18 |
   ...
   ```
5. **Chọn item để báo cáo** — menu mũi tên:
   ```
   Chọn item để report:
   ❯ Tất cả (all)
     Xem danh sách + chọn số (list)
     Nhập ID trực tiếp (ids)
     Thoát (quit)
   ```
   - `↑/↓` di chuyển, `Enter` chọn
   - Chọn `list` → hiện bảng đánh số, nhập STT (vd `1,3,5`) hoặc Enter = all
   - Chọn `ids` → nhập ID TFS (vd `7939,7940`) hoặc Enter = all
   - Chọn `quit` → thoát
   - Sai cú pháp/STT/ID → báo lỗi, hỏi lại
6. **Kết quả** — báo cáo vào `<năm>/<tháng>/<ngày>.md`:
   ```
   Tạo mới: 2026/8/19.md                          # file chưa có
   File đã có — đã update (append): 2026/8/19.md  # file có rồi
   ```

## Định dạng báo cáo

Theo `templetes/templete_main.md`, gồm 2 phần:

| Phần | Nội dung |
| --- | --- |
| `# templete chat` | Báo cáo nhân sự: công việc hôm nay, công việc ngày tiếp theo, vấn đề |
| `# templete lark` | Bảng: Task ID, Task Name, Task Link (link TFS), Type |

Mỗi item có dạng: `- Bug 7939: <tiêu đề> (0%)` — phần `(0%)` là tiến độ, TFS không có số này nên mặc định 0%, tự sửa tay sau khi tạo.

## Cấu hình

File `~/Documents/Report/config.json` (tự tạo bởi `run report init`):

```json
{
  "fullname": "Võ Phạm Tấn Đoan",
  "server": "https://tfs.tmtco.dev",
  "org": "TMTAICollection",
  "project": "Team_AI",
  "user": "doanvpt",
  "password": null
}
```

- `"password": null` → hỏi mật khẩu mỗi lần chạy; có giá trị → không hỏi (lưu plaintext)
- Đổi cấu hình: chạy lại `run report init` hoặc sửa file trực tiếp

## Biến môi trường (tùy chọn)

`TFS_USER` / `TFS_PASS` override config (hữu ích cho CI hoặc dùng tài khoản khác):

```bash
TFS_USER=other_user TFS_PASS=mat_khau run report
```

## Xử lý lỗi

| Thông báo | Nguyên nhân | Khắc phục |
| --- | --- | --- |
| `Request failed (22)` + JSON lỗi | Sai user/pass hoặc hết phiên | Kiểm tra lại tài khoản |
| `Request failed (28)` | Timeout — không nối được TFS | Kiểm tra mạng/VPN |
| `No work items assigned to you` | Tài khoản không có item nào | — |
| `Invalid IDs` | Nhập ID không phải số | Nhập lại, ví dụ `123,456` |

## Bảo mật

- Mật khẩu nhập ẩn (getpass)
- Lưu mật khẩu trong config là **plaintext** — chỉ lưu trên máy cá nhân; `config.json` đã chmod `600`
- Muốn bỏ lưu: chạy lại `run report init`, trả lời `N`
