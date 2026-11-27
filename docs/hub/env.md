---
section: env
updated: 2026-11-27
verified_commit: 1728129
---

| Name | Purpose | Used by | Secret |
|---|---|---|---|
| MODE | paper, demo hoặc live | bot | no |
| LIVE_CONFIRM | phải là I-ACCEPT-REAL-MONEY để chạy live | bot | no |
| BINANCE_API_KEY | key Binance (Futures, khoá IP) | bot | yes |
| BINANCE_API_SECRET | secret Binance | bot | yes |
| OPENAI_API_KEY | LLM OpenAI | bot | yes |
| ANTHROPIC_API_KEY | LLM Anthropic | bot | yes |
| ZAI_API_KEY | LLM z.ai | bot | yes |
| MOONSHOT_API_KEY | LLM Moonshot | bot | yes |
| OPENROUTER_API_KEY | LLM OpenRouter | bot | yes |
| OPENROUTER_MODEL | model OpenRouter | bot | no |
| OPENROUTER_PRICE_IN | USD / 1M token vào | bot | no |
| OPENROUTER_PRICE_OUT | USD / 1M token ra | bot | no |
| DISCORD_WEBHOOK_URL | báo động Discord, kênh #trading-bot (BrandonTa Lab) | bot | yes |
| DASH_USER | user dashboard | dashboard | no |
| DASH_PASSWORD | mật khẩu dashboard | dashboard | yes |
| LEVERAGE | đòn bẩy, tối đa 5 | bot | no |
| RISK_PCT | rủi ro mỗi lệnh, tối đa 0.02 | bot | no |
| FLOOR_EQUITY | dừng hẳn khi equity dưới mức này (USDT), mặc định 70 | bot (live) | no |
| SYMBOLS | danh sách cặp | bot, dashboard | no |
| DB_PATH | file SQLite | bot | no |
| PAPER_START | vốn paper | bot | no |
| BOT_NAME | nhãn trong báo động | bot | no |
| BOT_START | ISO time the bot began trading; earlier fills are the owner's | bot, dashboard | no |
| START_FUTURES | futures equity (USDT) at BOT_START | bot, dashboard | no |
| LLM_CREDIT | OpenRouter credit (USD) at BOT_START | bot, dashboard | no |
| LLM_USAGE_BASELINE | OpenRouter key usage (USD) at BOT_START | bot, dashboard | no |
