---
section: flows
updated: 2026-11-27
verified_commit: 1728129
---

## Chu kỳ giao dịch mỗi giờ
```flow
kind: logic
node: clock | Đóng nến 1h | step | +5 s sau mỗi giờ UTC
node: halt | Đang dừng hẳn? | decision | sự kiện halt trong SQLite
node: rec | Đối chiếu sàn | step | vị thế thiếu SL/TP thì đóng
node: snap | Snapshot | step | giá, ATR, RSI, EMA, funding, tin tức
node: llm | LLM | external | OpenRouter / OpenAI / …
node: risk | Kiểm tra rủi ro | decision | SL, R:R, confidence, số vị thế, dừng ngày
node: size | Tính khối lượng | step | 2% vốn / khoảng SL
node: bn | Binance | external | market + SL + TP
node: db | SQLite | store | events
edge: clock -> halt
edge: halt -> rec | không
edge: rec -> snap
edge: snap -> llm | JSON
edge: llm -> risk | quyết định
edge: risk -> size | đạt
edge: risk -> db | bị loại, ghi lý do
edge: size -> bn | đặt lệnh
edge: bn -> db | trade_open
```

## Owner theo dõi bot
```flow
kind: user
node: owner | Owner | actor
node: disc | Discord | external | báo lệnh, lỗi, tổng kết 8:00
node: dash | Dashboard | step | trade.brandondev.online
node: auth | Đúng mật khẩu? | decision | Basic auth
node: page | Vốn, lệnh, lý do LLM | step
node: clear | --clear-halt | step | sau khi dừng hẳn
edge: owner -> disc | nhận báo động
edge: owner -> dash | mở
edge: dash -> auth
edge: auth -> page | có
edge: owner -> clear | khi bot dừng hẳn
```

## Dữ liệu
```flow
kind: data
node: bpub | Binance public | external | nến, ticker, funding
node: rss | RSS tin tức | external | Cointelegraph, Decrypt, The Block
node: bot | Bot | step
node: llm | LLM provider | external
node: bpriv | Binance tài khoản | external | lệnh, vị thế, số dư
node: db | SQLite /data | store
node: dash | Dashboard | step
node: disc | Discord | external
edge: bpub -> bot
edge: rss -> bot | tiêu đề
edge: bot -> llm | snapshot
edge: llm -> bot | JSON quyết định
edge: bot -> bpriv | lệnh ký HMAC
edge: bot -> db | events
edge: db -> dash | đọc
edge: bot -> disc | webhook
```
