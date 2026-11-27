---
section: project
updated: 2026-11-27
verified_commit: 1728129
---

## One-liner
Bot LLM tự giao dịch Binance USDⓈ-M Futures (BTC/ETH/SOL) với vốn nhỏ, chạy 24/7 trên server.

## Short
Mỗi giờ bot gửi giá, chỉ báo và tin crypto mới cho một LLM; LLM đề xuất lệnh, code rủi ro duyệt (2%/lệnh, SL bắt buộc, dừng ngày 6%, dừng hẳn < 70 USDT) rồi tự đặt lệnh kèm SL/TP trên sàn. Dashboard riêng hiện vốn, lệnh và lý do của LLM.

## Long
Dự án cá nhân của owner: thử xem một LLM rẻ có thể giao dịch futures có lời với 100 USDT hay không, mà không để rủi ro vượt kiểm soát. LLM chỉ đề xuất; toàn bộ khối lượng, đòn bẩy (5x isolated) và giới hạn lỗ do code quyết định.

Không bán, không có khách hàng. Chi phí vận hành: LLM qua OpenRouter (~0.15 USD/tháng với model rẻ nhất) và một phần server dùng chung.

Repo còn chứa hai app cũ: `apps/p2p-dashboard` (Next.js) và `apps/chart-sync`.

## Market
- Không thương mại hoá; công cụ cá nhân.

## Links
| Name | URL |
|---|---|
| Dashboard | trade.brandondev.online (đăng nhập tại /login) |
| Health | https://trade.brandondev.online/health |
| Repo | https://github.com/Brandon-35/trading-bot |
