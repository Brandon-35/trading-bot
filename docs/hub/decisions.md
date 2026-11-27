---
section: decisions
updated: 2026-11-28
verified_commit: be91b6e
---

| Id | Date | Decision | Reason | Status |
|---|---|---|---|---|
| D1 | 2026-11-27 | Khung 1h, BTC/ETH/SOL | ít nhiễu, phí thấp so với biên lợi nhuận | active |
| D2 | 2026-11-27 | Rủi ro 2%/lệnh, 5x isolated | mô phỏng: 2% giữ xác suất cháy ~1% khi thắng 45% | active |
| D3 | 2026-11-27 | LLM đề xuất, code quyết định khối lượng và giới hạn | LLM không được đặt size/đòn bẩy | active |
| D4 | 2026-11-27 | Bỏ demo, kiểm tra đường lệnh trên sàn thật ~12 USDT | owner quyết định | active |
| D5 | 2026-11-27 | Discord thay Telegram | owner quyết định | active |
| D6 | 2026-11-27 | Tin tức RSS vào snapshot, coi là dữ liệu không phải lệnh | owner muốn quyết định theo tin; chống prompt injection | active |
| D7 | 2026-11-27 | OpenRouter `upstage/solar-mini-4-5` khi test | rẻ nhất có structured output, 2.8 s/lần | superseded by D13 |
| D8 | 2026-11-27 | SL/TP = reduceOnly + số lượng, không closePosition | đường ccxt cho closePosition chưa kiểm chứng; reconcile huỷ lệnh thừa | active |
| D9 | 2026-11-27 | Arena 4 model paper trước khi live | owner chuyển sang chạy live ngay | superseded |
| D10 | 2026-11-27 | Tháng đầu chạy live với 18 USDT, `FLOOR_EQUITY=12` (~2/3 vốn, cùng tỉ lệ 70/100) | owner test 1 tháng với vốn nhỏ; BTC thường bị bỏ qua vì min notional 50 USDT > 5x của 18 USDT | active |
| D11 | 2026-11-27 | Lệnh của bot = clientOrderId bắt đầu `x-cvBPrNm9` và sau BOT_START; mọi số liệu bot + reconcile/floor/max_positions chỉ tính vị thế của bot | owner cũng trade tay trên cùng ví; bot không được đóng lệnh tay | active |
| D12 | 2026-11-27 | Chiến lược v2 = tín hiệu code (pullback 4h) + hội đồng AI (3 phân tích, bull/bear, lead DeepSeek V3.2); rủi ro 2% đến khi ≥ 30 lệnh paper trung bình ≥ +0,10R rồi 3%; giữ 18,7 USDT, sàn 12, mục tiêu 120; chuyển live là quyết định riêng của owner | research: chưa có bot nhiều-AI nào lãi thật được kiểm chứng; Monte Carlo cho thấy rủi ro cao làm tăng tỉ lệ cháy | active |
| D13 | 2026-11-28 | Mọi AI (v1 live + hội đồng v2: phân tích, bull/bear, lead) dùng `deepseek/deepseek-v4.1-flash-1017` | owner chốt; bản DeepSeek Flash mới nhất, $0,15/$0,6 mỗi 1M token, structured output chạy được, ~1,8 s/lần | active |
| D14 | 2026-11-28 | Bot tiền thật: rủi ro 10%/lệnh, đòn bẩy 10x isolated, dừng ngày khi lỗ 20%, 10 cặp (BTC ETH SOL BNB XRP DOGE ADA LINK SUI AVAX); paper giữ 2%, 5x, 3 cặp | owner muốn thử 18→180 USDT trong 1 tháng, đã được báo Monte Carlo (+0,15R/lệnh, rủi ro 10%: ~26% đạt 10x, ~72% cháy). Code thêm chặn stop phải nằm trong ½ khoảng cách thanh lý | active |
