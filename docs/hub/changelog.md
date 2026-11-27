---
section: changelog
updated: 2026-11-27
verified_commit: bc3a991
---

## 0.1.0 — 2026-11-27
- Bot LLM Binance USDⓈ-M: risk engine, broker Binance + paper, tin tức RSS, Discord, tự chọn LLM, OpenRouter.
- Dashboard đọc-only có Basic auth.
- Dashboard: trang đăng nhập thay Basic auth (cookie HttpOnly, SameSite=Strict, Secure, 7 ngày; sai mật khẩu chờ 1 s; chặn POST khác origin). Cảnh báo Discord vào kênh #trading-bot của BrandonTa Lab.
- Dashboard v2: giao diện tiếng Việt màu Binance, logo + tên "Bot Giao Dịch", biểu đồ nến, vốn tính từ 2026-11-27 13:25 ICT (18.7392 USDT + 2 USD credit LLM), tab Tài khoản toàn vòng đời. Bot đồng bộ fills/income/vị thế vào SQLite; dashboard không giữ key Binance.
- Bot chỉ đụng vị thế và lệnh trigger có prefix của nó; không mở lệnh trên cặp đang có lệnh tay.
- Kiểm tra key live: khoá IP, rút tiền tắt, Futures bật.
