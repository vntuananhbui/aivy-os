
---
name: sharepoint
description: Đọc và trích dẫn nội dung từ các file SharePoint/OneDrive mà người dùng đã kết nối. Dùng khi câu hỏi liên quan tới tài liệu, báo cáo, hoặc dữ liệu nội bộ của người dùng thay vì thông tin công khai trên web.
category: access
trigger: Câu hỏi nhắc tới tài liệu/file/report của người dùng, hoặc khi SharePoint connector đã được kết nối (connected=true) và câu hỏi có thể được trả lời từ các file đã chọn.
status: seed
has_executor: true
---
# sharepoint

## Mục tiêu

Trả lời câu hỏi dựa trên nội dung file SharePoint/OneDrive đã kết nối, với độ chính xác trích dẫn cao —
không bịa số liệu, luôn cho biết câu trả lời lấy từ file nào.

## Khi nào dùng

- Người dùng hỏi về nội dung tài liệu nội bộ ("báo cáo Q3 nói gì về...", "file này có đề cập...")
- Cần đối chiếu số liệu/claim với nguồn gốc trong tài liệu đã kết nối
- Câu hỏi cần tổng hợp thông tin từ nhiều file (không chỉ 1 file)

## Không dùng khi

- Câu hỏi về thông tin công khai trên internet (dùng web_search)
- SharePoint chưa được kết nối hoặc chưa có file nào được chọn

## Quy trình đọc 1 file

1. `search(query)` để tìm đúng file/id trong danh sách đã kết nối.
2. `read(item_id)` để lấy nội dung — kết quả LUÔN kèm tên file + URL, không chỉ text thô.
3. Nếu câu hỏi có số liệu/con số cụ thể → tìm khớp chính xác (grep) đoạn chứa số liệu đó trước.
   Chỉ khi không tìm thấy khớp chính xác mới suy luận/diễn giải theo ngữ cảnh xung quanh.
4. Trích **nguyên văn** câu/đoạn hỗ trợ câu trả lời — không diễn giải lại số liệu.

## Quy trình khi câu hỏi cần nhiều file (autoresearch pattern)

Khi 1 file không đủ trả lời:

1. Liệt kê các khía cạnh câu hỏi cần (search nhiều query khác nhau thay vì 1 query mơ hồ).
2. Với mỗi khía cạnh, search → read file liên quan nhất.
3. Nếu 2 file cho thông tin mâu thuẫn nhau, nêu rõ cả hai và sự khác biệt — không tự ý chọn 1 bên.
4. Dừng lại khi đã đủ bằng chứng trả lời tất cả khía cạnh của câu hỏi — không đọc thêm file không liên quan.

## Phân loại mức độ hỗ trợ (khi cần nêu rõ độ tin cậy)

| Mức        | Ý nghĩa                                                            |
| ----------- | -------------------------------------------------------------------- |
| Direct      | File nêu đúng số liệu/claim, cùng chiều, cùng bối cảnh     |
| Partial     | File hỗ trợ ý chính nhưng khác số liệu/phạm vi/thời điểm |
| Indirect    | File hỗ trợ logic nền nhưng không nói thẳng claim này        |
| Contradicts | File có số liệu/kết luận mâu thuẫn với claim                 |
| Not Found   | Không tìm thấy trong các file đã kết nối                     |

Mặc định chọn **Partial** thay vì **Direct** nếu có bất kỳ khác biệt nào về phạm vi/thời điểm/số liệu.

## Trích dẫn

Cách gọi tool `cite(url, title, quote)` là quy tắc chung cho mọi nguồn (xem system prompt) —
không lặp lại ở đây. Riêng với SharePoint: `url`/`title` bắt buộc lấy từ
`SOURCE URL`/`SOURCE TITLE` trong header của `sharepoint_read` hoặc kết quả
`sharepoint_search`; không dùng URL trang web nằm bên trong nội dung tài liệu.
`quote` phải là **nguyên văn**, không diễn giải lại số liệu.

Nếu không tìm thấy trong các file đã kết nối, nói rõ "không tìm thấy trong tài liệu đã kết nối" —
không suy đoán hoặc lấy từ kiến thức chung để thay thế, và không gọi `cite` khi không có nguồn thật.

## Lỗi thường gặp cần tránh

- Làm tròn/diễn giải lại số liệu trong `quote` thay vì giữ nguyên văn
- Chỉ đọc 1 file rồi kết luận trong khi câu hỏi cần đối chiếu nhiều file
