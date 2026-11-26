# trading-bot

Open-source crypto trading bot workspace: strategy engine, exchange connectors, backtesting,
and the dashboards that watch them.

> [!WARNING]
> Status: planning. No order-placing code exists yet. Nothing here is financial advice;
> live trading will stay opt-in and paper trading is the default.

## Layout

| Path | What | Origin |
|------|------|--------|
| `apps/p2p-dashboard` | P2P trading history, portfolio analysis, charts (React + Vite + Recharts) | imported from `P2P-Crypto-Dashboard` with full git history |
| `apps/chart-sync` | Multi-chart TradingView board with synced global controls (React + Vite) | imported from `CryptoSync-Pro` with full git history |
| `bot/` | LLM-driven Binance USDⓈ-M futures bot (Python, ccxt), paper / demo / live | new |
| `packages/` | Reserved | new |
| `docs/` | Plan and design notes | new |

## Run an app

```bash
cd apps/chart-sync   # or apps/p2p-dashboard
npm install
npm run dev
```

## Run the bot

Paper trading is the default; live trading needs `MODE=live` **and** `LIVE_CONFIRM=I-ACCEPT-REAL-MONEY`.

```bash
cd bot
uv sync && uv run pytest -q          # tests
cp .env.example .env && chmod 600 .env   # fill in the LLM keys
docker compose up -d --build         # 4-model paper arena
docker compose exec arena-gpt python -m trader.report /data/gpt.db /data/claude.db /data/glm.db /data/kimi.db
```

Risk rules live in `bot/trader/risk.py` (2 % risk per trade, stop-loss always on the exchange,
6 % daily stop, full stop below 70 USDT). Clear a full stop with `python -m trader.main --clear-halt`.

## License

MIT, see `LICENSE`.
