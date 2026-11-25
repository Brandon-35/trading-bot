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
| `packages/` | Bot core (planned, see `docs/PLAN.md`) | new |
| `docs/` | Plan and design notes | new |

## Run an app

```bash
cd apps/chart-sync   # or apps/p2p-dashboard
npm install
npm run dev
```

## License

MIT, see `LICENSE`.
