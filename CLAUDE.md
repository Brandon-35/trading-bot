# trading-bot

- `bot/`: LLM-driven Binance USDⓈ-M futures bot (Python 3.12, ccxt). Tests: `cd bot && uv run pytest -q`.
- Production: server-brandon-service `/opt/services/trading-bot` (rsync `bot/` + docker compose, profiles `live` and `dashboard`); dashboard https://trade.brandondev.online. Deploy steps: `docs/hub/infra.md`.
- Real money: never start or change the `live` service without the owner's explicit go; `.env` on the server holds the keys (mode 600), never print or commit it.
- Plan and decisions: `docs/plans/2026-11-27-llm-futures-bot.md`, issue #1.

## Portfolio Hub docs (standard v1)
- `docs/hub/` is read by the Portfolio Hub dashboard straight from this repo. Spec: `Brandon-35/ideal` → `hub/standard/SPEC.md`.
- Any product change (decision, release, feature, cost, env name, channel, infra, roadmap, stack version) updates the matching `docs/hub/*.md` in the same PR, bumps its `updated` and `verified_commit`, and ends with `hub-lint .` at 0 errors.
- `env.md` lists names only. Never write a secret value in any doc.
