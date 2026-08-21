<template>
    <div class="card">
        <h3>Hướng dẫn sử dụng & Templates</h3>
        <p class="line-height-3">Tài liệu cho app tạo báo cáo công việc hàng ngày từ work items TFS / Azure DevOps.</p>

        <h5>1. Các bước tạo report</h5>
        <ul class="line-height-3">
            <li><span class="text-primary font-medium">Đăng nhập</span> bằng tài khoản TFS (NTLM) hoặc PAT tại trang Login.</li>
            <li><span class="text-primary font-medium">Chọn dự án</span>: chọn Collection rồi chọn Project cần báo cáo.</li>
            <li>Vào trang <span class="text-primary font-medium">Report</span> — danh sách work items gán cho bạn (@me) được tải tự động.</li>
            <li>Dùng <span class="text-primary font-medium">Tìm kiếm</span> (ID hoặc tiêu đề, có/không dấu), các bộ lọc <span class="text-primary font-medium">Trạng thái / Sprint / Loại / Parent</span>, lọc theo <span class="text-primary font-medium">ngày tạo pull request</span> hoặc <span class="text-primary font-medium">theo số PR</span>.</li>
            <li>Tick item vào cột <span class="text-primary font-medium">Hôm nay</span> (công việc đã làm) hoặc <span class="text-primary font-medium">Mai</span> (kế hoạch ngày tiếp theo) — 2 nhóm này khác nhau, chọn riêng.</li>
            <li>Chọn <span class="text-primary font-medium">Ngày báo cáo</span> rồi bấm <span class="text-primary font-medium">Tạo report</span>.</li>
            <li>Report hiện trong dialog kết quả: xem trước (chat / Lark / cả hai, có tab sửa tay), <span class="text-primary font-medium">Copy</span> hoặc <span class="text-primary font-medium">Tải file .md</span>. Không ghi đĩa tự động.</li>
        </ul>

        <h5>2. Template Chat</h5>
        <pre class="app-code"><code>*Báo cáo nhân sự* &lt;dd/mm/yyyy&gt;
*Nhân sự:* &lt;fullname&gt;
*Công việc:*
- &lt;Type&gt; &lt;ID&gt;: &lt;title&gt; (&lt;progress&gt;%)
- ...
*Công việc ngày tiếp theo:*
- &lt;Type&gt; &lt;ID&gt;: &lt;title&gt;
- ...
*Vấn đề:*
- None</code></pre>
        <p class="line-height-3">Nhóm "Hôm nay" hiển thị % hoàn thành của từng item (xem mục 5); nhóm "Ngày tiếp theo" không kèm %.</p>

        <h5>3. Template Lark</h5>
        <pre class="app-code"><code>| Status | Start date | End date | Note | Type | Task ID | Task Name | Task Link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| &lt;status&gt; | &lt;start date&gt; | &lt;end date&gt; |  | &lt;type&gt; | &lt;id&gt; | &lt;title&gt; | &lt;link&gt; |</code></pre>
        <ul class="line-height-3">
            <li><span class="text-primary font-medium">Start date</span> = ngày item vào trạng thái khớp rule "Trạng thái bắt đầu" trong Cài đặt (đọc lịch sử revisions của TFS). Không có rule / không khớp thì fallback ngày báo cáo (item "Mai" dùng ngày mai).</li>
            <li><span class="text-primary font-medium">End date</span> = ngày item vào trạng thái khớp rule "Trạng thái kết thúc". Không có thì để trống.</li>
            <li>Report cuối = phần Chat + phần Lark (hợp nhất 2 nhóm, bỏ item trùng lặp).</li>
        </ul>

        <h5>4. Quy ước</h5>
        <ul class="line-height-3">
            <li>Ngày theo định dạng <span class="text-primary font-medium">dd/mm/yyyy</span>.</li>
            <li>Nhóm nào bỏ trống để dòng <span class="text-primary font-medium">- ...</span>.</li>
            <li>Link work item dạng <span class="text-primary font-medium">&lt;server&gt;/&lt;collection&gt;/&lt;project&gt;/_workitems/edit/&lt;id&gt;</span>.</li>
            <li>Title giữ nguyên từ TFS; ký tự <span class="text-primary font-medium">|</span> trong title được escape <span class="text-primary font-medium">\|</span> để không vỡ bảng Lark.</li>
            <li>Type lấy từ trường <span class="text-primary font-medium">System.WorkItemType</span> của TFS.</li>
        </ul>

        <h5>5. Cài đặt (icon bánh răng trên topbar)</h5>
        <ul class="line-height-3">
            <li><span class="text-primary font-medium">Tên hiển thị</span>: điền sẵn display name thật từ TFS; checkbox <span class="text-primary font-medium">"Dùng username khi không có tên hiển thị"</span> quyết định dòng <i>Nhân sự</i> fallback về username hay để trống.</li>
            <li><span class="text-primary font-medium">Tính % công việc</span>:
                <ul class="line-height-3">
                    <li><span class="text-primary font-medium">Theo Remaining/Completed work</span>: % = Completed / (Completed + Remaining). Item không có số work thì fallback theo trạng thái.</li>
                    <li><span class="text-primary font-medium">Theo trạng thái</span>: Closed / Resolved / Done / Completed / Removed / Finished = 100%, còn lại 0%.</li>
                </ul>
            </li>
            <li><span class="text-primary font-medium">Trạng thái bắt đầu / kết thúc (Lark)</span>: chọn Loại work item + Trạng thái rồi bấm <i>+</i> để thêm vào danh sách. Loại đã có thì bấm nút cập nhật (bút chì) đổi trạng thái. Trạng thái bắt đầu và kết thúc của cùng một loại phải khác nhau.</li>
            <li>Mỗi dòng rule có 2 checkbox:
                <ul class="line-height-3">
                    <li><span class="text-primary font-medium">Tôi chuyển</span>: chỉ tính khi chính bạn thực hiện lần chuyển trạng thái; bỏ check = bất kỳ ai.</li>
                    <li><span class="text-primary font-medium">Sau cùng</span>: item vào trạng thái nhiều lần thì lấy ngày lần cuối; bỏ check = lần đầu.</li>
                </ul>
            </li>
            <li>Loại bỏ chọn trong rule (nếu có) áp cho <span class="text-primary font-medium">mọi loại</span>.</li>
            <li>Icon <span class="text-primary font-medium">↻ cạnh nút đóng dialog</span>: áp lại cấu hình mặc định từ <span class="text-primary font-medium">default.json</span> (chưa lưu — bấm Lưu để ghi).</li>
            <li>Cấu hình lưu trong <span class="text-primary font-medium">backend/config.json</span> (ghi đè từng key khi bấm Lưu); giá trị mặc định nằm ở <span class="text-primary font-medium">backend/default.json</span> — key nào bị xóa/đặt null trong config.json thì rơi về default.</li>
            <li>Sau khi Lưu, trang Report tự nạp lại dữ liệu (%, ngày start/end, tên) cho phần xem trước — không cần refresh.</li>
        </ul>
    </div>
</template>
