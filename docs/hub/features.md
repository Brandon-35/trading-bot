---
section: features
updated: 2026-11-27
verified_commit: f673cf5
---

| Surface | Feature | Status | Since |
|---|---|---|---|
| bot | Chu kỳ 1h: snapshot giá + ATR/RSI/EMA 15m/1h/4h + funding gửi LLM | shipped | 2026-11-27 |
| bot | Tin crypto 12h gần nhất (Cointelegraph, Decrypt, The Block) trong snapshot | shipped | 2026-11-27 |
| bot | Risk engine: 2%/lệnh, SL 0.5–3×ATR, R:R ≥ 1.5, tối đa 2 vị thế, dừng ngày 6%, dừng hẳn < 70 USDT | shipped | 2026-11-27 |
| bot | Lệnh market + SL/TP trên sàn, lỗi đặt SL thì đóng ngay, đối chiếu sàn mỗi 20 s | shipped | 2026-11-27 |
| bot | Tự chọn LLM theo key có sẵn (OpenAI, Anthropic, z.ai, Moonshot, OpenRouter) | shipped | 2026-11-27 |
| bot | Paper broker + arena nhiều model | shipped | 2026-11-27 |
| alerts | Báo động Discord webhook | shipped | 2026-11-27 |
| dashboard | Trang vốn, vị thế, lệnh, quyết định LLM, chi phí (trang đăng nhập, phiên 7 ngày, nút đăng xuất) | shipped | 2026-11-27 |
| dashboard | Giao diện v2 tiếng Việt màu Binance: biểu đồ nến + điểm vào/ra của bot, đường giá trị vốn (vốn đầu + credit LLM), lời/lỗ theo ngày, vị thế realtime, lịch sử lệnh, quyết định LLM | shipped | 2026-11-27 |
| dashboard | Tab Tài khoản: lời/lỗ toàn bộ vòng đời Futures (file xuất Binance từ 2019 + API), theo tháng, theo cặp | shipped | 2026-11-27 |
| bot | Chỉ quản lý vị thế/lệnh của chính bot (clientOrderId `x-cvBPrNm9`); lệnh tay không bị đụng | shipped | 2026-11-27 |
| bot | Chạy tiền thật 24/7 (service `live`) | shipped | 2026-11-27 |
| bot | Bộ backtest có phí (`python -m trader.backtest`), 4 loại tín hiệu, cổng lợi thế ≥ +0,10R | shipped | 2026-11-27 |
| bot | v2: quét 30 altcoin mỗi 15 phút, tín hiệu pullback 4h, lọc đám đông (funding + long/short) | building | - |
| bot | Hội đồng AI: 3 phân tích → bull/bear tranh luận → lead DeepSeek chốt, trần $0,10/ngày | building | - |
| bot | Quản lý vốn v2: 2%/lệnh đến khi chứng minh lợi thế rồi 3%, tổng rủi ro ≤ 10%, thanh lý xa ≥ 2× SL, chốt nửa 2R + trailing | building | - |
| dashboard | Tab "Thử nghiệm v2" (so sánh 2 nhánh paper) và "Hội đồng AI" (biên bản tranh luận) | shipped | 2026-11-27 |
| dashboard | Giao diện điện thoại: 6 tab (Lịch sử và Thử nghiệm có mục con), thanh tab dưới đáy + bảng thành thẻ; tab "Hệ thống" (báo cáo đầy đủ); quy đổi VND theo tỉ giá Binance P2P (`/api/fx`); số định dạng vi-VN | shipped | 2026-11-27 |
