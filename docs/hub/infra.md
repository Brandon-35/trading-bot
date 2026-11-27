---
section: infra
updated: 2026-11-27
verified_commit: 1728129
---

| Component | Where | Address | Notes |
|---|---|---|---|
| Stack | server-brandon-service (5.189.155.78) | /opt/services/trading-bot | rsync từ repo `bot/`, docker compose |
| live bot | container trading-bot-live-1 | - | profile `live`, MODE=live, DB /data/live.db |
| paper v2 | containers trading-bot-paper-signal-1, trading-bot-paper-committee-1 | - | profile `paper2`, MODE=paper, STRATEGY=v2, DB /data/paper_signal.db, /data/paper_committee.db; start: `docker compose --profile paper2 up -d --build paper-signal paper-committee` |
| dashboard | container trading-bot-dashboard-1 | 127.0.0.1:8090, edge :8080 | trang đăng nhập + cookie phiên ký HMAC (7 ngày) |
| Volume | docker volume trading-bot_data | /data | SQLite mỗi bot |
| Edge | Caddy `/opt/edge/caddy-sites/trading-bot.caddy` | trade.brandondev.online | repo server-services |
| SNI | /opt/stalwart-mail/proxy/nginx.conf | :443 → 127.0.0.1:8444 | repo stalwart-mail |
| DNS | iNET wildcard | *.brandondev.online | không cần record riêng |
| Binance key | IP whitelist 5.189.155.78 | - | Reading + Futures, rút tiền tắt |

## Deploy
```bash
rsync -az --delete --exclude .venv --exclude data --exclude .env --exclude __pycache__ bot/ server-brandon-service:/opt/services/trading-bot/
ssh server-brandon-service 'cd /opt/services/trading-bot && docker compose --profile live up -d --build && docker compose up -d --build dashboard'
```

## Rollback
```bash
ssh server-brandon-service 'cd /opt/services/trading-bot && docker compose --profile live stop live'
git checkout <previous-sha> -- bot && rsync -az --delete --exclude .venv --exclude data --exclude .env bot/ server-brandon-service:/opt/services/trading-bot/
```
Dừng bot không đóng vị thế: SL/TP vẫn nằm trên sàn.

## Health
https://trade.brandondev.online/health → 200 `ok` = đang chạy; `/` chuyển tới `/login` khi chưa đăng nhập
