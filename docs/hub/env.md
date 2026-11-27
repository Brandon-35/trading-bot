---
section: env
updated: 2026-11-28
verified_commit: af4e993
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
| STRATEGY | v1 (mặc định, đang chạy tiền thật) hoặc v2 (chỉ paper đến khi owner đồng ý) | bot | no |
| ARM | nhánh v2: signal (chỉ tín hiệu) hoặc committee (hội đồng AI) | bot | no |
| SIGNAL | tín hiệu v2 (mặc định pullback 4h) | bot | no |
| UNIVERSE_N | số altcoin quét (mặc định 30 cho paper) | bot | no |
| RISK_PCT_PROVEN | rủi ro/lệnh sau khi qua cổng lợi thế (≥ 30 lệnh, ≥ +0,10R), mặc định 0.03 | bot | no |
| FLOOR_EQUITY_PAPER | sàn dừng của nhánh paper v2 | bot | no |
| LEAD_MODEL | AI lead của hội đồng (mặc định deepseek/deepseek-v4.1-flash-1017) | bot | no |
| ANALYST_MODEL | AI phân tích + bull/bear (mặc định deepseek/deepseek-v4.1-flash-1017) | bot | no |
| LLM_DAILY_USD | trần chi phí AI mỗi ngày UTC (mặc định 0.10) | bot | no |
| ARM_DBS | DB của 2 nhánh paper cho dashboard | dashboard | no |
