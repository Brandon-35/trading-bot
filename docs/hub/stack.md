---
section: stack
updated: 2026-11-27
verified_commit: 1728129
---

| Layer | Tech | Version | Why |
|---|---|---|---|
| Language | Python | 3.12 | ccxt + SDK LLM đầy đủ nhất |
| Exchange | `ccxt` | 4.5.94 | Binance USDⓈ-M, algo order endpoint |
| LLM client | `openai` | 3.60.0 | một client cho mọi provider OpenAI-compatible |
| Validation | `pydantic` | 2.14.4 | kiểm tra JSON quyết định của LLM |
| HTTP | `httpx` | 0.29.0 | RSS tin tức, Discord webhook |
| Storage | SQLite | stdlib | event log append-only, một file mỗi bot |
| Dashboard | http.server | stdlib | trang đọc-only, không thêm dependency |
| Runtime | Docker Compose | - | profiles: live, gpt, claude, glm, kimi, dashboard |
| Edge | Caddy | - | trade.brandondev.online qua edge Caddy + SNI proxy |
