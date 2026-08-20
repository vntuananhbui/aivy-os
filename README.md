# aivy-os

## 🏃 Cách chạy

**1. Cài đặt** (yêu cầu Python ≥ 3.11, Node.js ≥ 20.9 nếu cần cả web frontend):

```bash
./install.sh
source .venv/bin/activate
```

**2. Cấu hình lần đầu** — lệnh đầu tiên sẽ tự mở setup wizard để chọn provider và nhập API key (ghi vào `.env`). Có thể cấu hình lại bất cứ lúc nào bằng `searchos --setup`, hoặc tự copy `.env.example` → `.env` rồi điền key thủ công.

**3. Chạy:**

```bash
# Chạy 1 câu hỏi trực tiếp từ CLI
searchos "Top-5 universities per subject in the 2025 QS rankings, with application deadlines"

# Hoặc mở TUI full-screen (không truyền query) để xem tiến trình real-time
searchos

# Hoặc chạy Web UI (REST/WS API :8000 + frontend :3000)
./web/start.sh
```
