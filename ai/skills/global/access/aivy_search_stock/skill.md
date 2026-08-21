---
name: aivy_search_stock
description: Tra cứu giá cổ phiếu Việt Nam (HOSE/HNX/UPCOM) theo thời gian thực từ FireAnt.vn — giá hiện tại, biến động, khối lượng, vốn hóa. Nhận mã như DPM, VCB, FPT.
category: access
trigger: Câu hỏi hỏi về giá/biến động/khối lượng giao dịch của một hoặc nhiều mã cổ phiếu Việt Nam cụ thể.
status: seed
has_executor: true
---

# aivy_search_stock

## Mục tiêu
Trả lời câu hỏi về giá cổ phiếu Việt Nam hiện tại (HOSE/HNX/UPCOM) bằng dữ liệu thật lấy từ FireAnt.vn,
không suy đoán hay dùng số liệu cũ từ kiến thức nền.

## Khi nào dùng
- Người dùng hỏi giá/biến động của 1 hoặc nhiều mã cổ phiếu cụ thể ("giá DPM hôm nay", "so sánh VCB BID CTG")
- Cần khối lượng giao dịch, vốn hóa, hoặc % thay đổi trong phiên

## Không dùng khi
- Câu hỏi về cổ phiếu quốc tế (không phải HOSE/HNX/UPCOM)
- Câu hỏi phân tích/dự báo dài hạn không cần giá real-time

## Cách gọi
`check_stock(symbols)` — truyền 1 hoặc nhiều mã, cách nhau bởi dấu phẩy/khoảng trắng, tối đa 5 mã/lần gọi.

## Cách hoạt động
Không phụ thuộc trình duyệt tự động ngoài (không dùng openclaw): tìm trang FireAnt của mã qua search
provider đang cấu hình (`SF_SEARCH_PROVIDER`), fetch trang bằng backend đang cấu hình (`SF_BROWSER_BACKEND`,
mặc định `jina` — render JS), rồi trích giá/khối lượng/vốn hóa từ nội dung trả về.

## Lỗi thường gặp cần tránh
- Không tìm thấy giá do trang FireAnt đổi layout hoặc mã không tồn tại → trả lỗi rõ ràng, không bịa số liệu
- Không trộn dữ liệu cũ (kiến thức nền) với dữ liệu vừa fetch — luôn ưu tiên kết quả tool
