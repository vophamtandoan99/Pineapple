# templete chat

```
*Báo cáo nhân sự* <dd/mm/yyyy>
*Nhân sự:* <fullname>
*Công việc:*
- <Bug|Task> <ID>: <title> (<progress>%)
- ...
*Công việc ngày tiếp theo:*
- <Bug|Task> <ID>: <title> (<progress>%)
- ...
*Vấn đề:*
- None
```

## Quy ước

- Progress mặc định `(0%)` — TFS không cấp, sửa tay sau khi tạo
- Ngày theo định dạng `dd/mm/yyyy`
- Mỗi item một dòng `- <Type> <ID>: <title> (0%)`
- "Công việc" và "Công việc ngày tiếp theo" là 2 nhóm item KHÁC NHAU, chọn riêng
  (UI: cột "Hôm nay" / "Mai"; CLI: pick lần 2 sau khi chọn hôm nay)
- Nhóm nào bỏ trống → để dòng `- ...`
