<template>
    <div class="card">
        <h3>Hướng dẫn sử dụng & Templates</h3>
        <p class="line-height-3">Tài liệu cho app tạo báo cáo công việc hàng ngày từ work items TFS / Azure DevOps.</p>

        <h5>1. Các bước tạo report</h5>
        <ul class="line-height-3">
            <li><span class="text-primary font-medium">Đăng nhập</span> bằng tài khoản TFS (NTLM) tại trang Login.</li>
            <li><span class="text-primary font-medium">Chọn dự án</span>: chọn Collection rồi chọn Project cần báo cáo.</li>
            <li>Vào trang <span class="text-primary font-medium">Report</span> — danh sách work items gán cho bạn (@me) được tải tự động.</li>
            <li>Dùng <span class="text-primary font-medium">Tìm kiếm</span> (ID hoặc tiêu đề) và <span class="text-primary font-medium">Trạng thái</span> để lọc.</li>
            <li>Tick item vào cột <span class="text-primary font-medium">Hôm nay</span> (công việc đã làm) hoặc <span class="text-primary font-medium">Mai</span> (kế hoạch ngày tiếp theo) — 2 nhóm này khác nhau, chọn riêng.</li>
            <li>Chọn <span class="text-primary font-medium">Ngày báo cáo</span> rồi bấm <span class="text-primary font-medium">Tạo report</span>.</li>
            <li>File lưu tại <span class="text-primary font-medium">&lt;repo&gt;/&lt;yyyy&gt;/&lt;m&gt;/&lt;d&gt;.md</span>; nếu file đã tồn tại thì report mới được <span class="text-primary font-medium">append</span> vào dưới.</li>
        </ul>

        <h5>2. Template Chat</h5>
        <pre class="app-code"><code>*Báo cáo nhân sự* &lt;dd/mm/yyyy&gt;
*Nhân sự:* &lt;fullname&gt;
*Công việc:*
- &lt;Bug|Task&gt; &lt;ID&gt;: &lt;title&gt; (&lt;progress&gt;%)
- ...
*Công việc ngày tiếp theo:*
- &lt;Bug|Task&gt; &lt;ID&gt;: &lt;title&gt; (&lt;progress&gt;%)
- ...
*Vấn đề:*
- None</code></pre>

        <h5>3. Template Lark</h5>
        <pre class="app-code"><code>| Status | Start date | End date | Note | Type | Task ID | Task Name | Task Link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| &lt;status&gt; | &lt;current date&gt; | &lt;none&gt; | &lt;none&gt; | &lt;type = Task|Bug&gt; | &lt;id&gt; | &lt;title&gt; | &lt;link&gt; |</code></pre>
        <p class="line-height-3">Report cuối = phần Chat + phần Lark (hợp nhất 2 nhóm, bỏ item trùng lặp).</p>

        <h5>4. Quy ước</h5>
        <ul class="line-height-3">
            <li>Progress mặc định <span class="text-primary font-medium">(0%)</span> — TFS không cấp, sửa tay sau khi tạo.</li>
            <li>Ngày theo định dạng <span class="text-primary font-medium">dd/mm/yyyy</span>.</li>
            <li>Mỗi item một dòng: <span class="text-primary font-medium">- &lt;Type&gt; &lt;ID&gt;: &lt;title&gt; (0%)</span>.</li>
            <li>Nhóm nào bỏ trống để dòng <span class="text-primary font-medium">- ...</span>.</li>
            <li>Link work item dạng <span class="text-primary font-medium">&lt;server&gt;/&lt;org&gt;/&lt;project&gt;/_workitems/edit/&lt;id&gt;</span>.</li>
            <li>Title giữ nguyên từ TFS; ký tự <span class="text-primary font-medium">|</span> trong title được escape <span class="text-primary font-medium">\|</span> để không vỡ bảng Lark.</li>
            <li>Type lấy từ trường <span class="text-primary font-medium">System.WorkItemType</span> của TFS.</li>
        </ul>
    </div>
</template>
