---
name: jira
description: Đọc và trích dẫn nội dung từ các Jira issue mà người dùng đã kết nối, đồng thời có thể tạo/sửa/chuyển trạng thái/bình luận issue khi được yêu cầu rõ ràng. Dùng khi câu hỏi liên quan tới task/ticket/bug trên Jira thay vì thông tin công khai trên web.
category: access
trigger: Câu hỏi nhắc tới task/ticket/issue/sprint của người dùng, hoặc khi Jira connector đã được kết nối (connected=true), hoặc người dùng yêu cầu tạo/sửa/chuyển trạng thái/bình luận một issue.
status: seed
has_executor: true
---
# jira

## Mục tiêu

Trả lời câu hỏi dựa trên nội dung issue Jira đã kết nối (Q&A), và thực hiện thay đổi thật (tạo/sửa/chuyển
trạng thái/bình luận) khi người dùng yêu cầu rõ ràng — không bịa nội dung, không tự ý ghi khi ý định chưa rõ.

## Đọc (Q&A)

1. `search(query)` — `query` là **1 mệnh đề JQL thật**, không phải chuỗi từ khoá tự do — được dùng nguyên văn
   (AND với project scope đã chọn lúc kết nối, nếu có). Tìm từ khoá tự do thì viết `text ~ "từ khoá"`; lọc theo
   project thì dùng đúng **project key** (vd `KAN`), không phải tên hiển thị project (vd "AIVY" chỉ là tên, key
   thật có thể khác — nếu không chắc key, `text ~ "AIVY"` vẫn tìm theo tên/nội dung được). Ví dụ khác:
   `project = KAN AND status != Done`, `key ~ "KAN-*"`. Query rỗng/"*" liệt kê issue mới cập nhật gần nhất.
2. `read(item_id)` (item_id = issue key, vd `PROJ-123`) — trả về nội dung LUÔN kèm key + title + URL, không chỉ
   text thô. Nếu nội dung dài, kết quả kết thúc bằng gợi ý gọi lại với `offset` để đọc tiếp.
3. Trích **nguyên văn** đoạn hỗ trợ câu trả lời khi cần dẫn chứng cụ thể (số liệu, quyết định, deadline).

## Ghi (tạo/sửa/chuyển trạng thái/bình luận)

Đây là hành động có tác dụng phụ thật trên hệ thống Jira của người dùng — **chỉ thực hiện khi ý định đã rõ
ràng**. Nếu thiếu thông tin bắt buộc (project, loại issue, issue nào, trạng thái nào), hỏi lại thay vì đoán.

- `create_issue(project, summary, description, issue_type)` — tạo issue mới. Mô tả truyền plain text (client tự
  chuyển sang định dạng Jira yêu cầu) — không cần agent tự viết Jira wiki markup.
- `update_issue(key, fields)` — sửa field (vd `{"summary": "..."}`, `{"priority": {"name": "High"}}`).
- `add_comment(key, text)` — thêm bình luận.
- `transition_issue(key, transition_name)` — chuyển trạng thái theo **tên transition** (vd "In Progress", "Done"),
  không phải tên status đích — nếu tên không khớp, lỗi trả về sẽ liệt kê các transition khả dụng trên issue đó,
  dùng lại chính xác 1 trong các tên đó.

Sau khi ghi thành công, LUÔN nêu rõ issue key + link (`{site_url}/browse/{KEY}`) trong câu trả lời để người dùng
tự kiểm tra lại.

## Trích dẫn

Cách gọi tool `cite(url, title, quote)` là quy tắc chung cho mọi nguồn (xem system prompt) — không lặp lại ở
đây. Riêng với Jira: `url` là link `{site_url}/browse/{KEY}`, `title` là summary của issue.
