# Plan — trading-bot

Status: Phase 0–1 done (2026-11-26). Repo public at https://github.com/Brandon-35/trading-bot.

## Goal

One public, open-source repo for an automated crypto trading bot. The two existing chart
dashboards become its monitoring features.

## Decisions

- Repo name `trading-bot` under `Brandon-35`, public, MIT license.
- The two old repos are imported with `git subtree add` so their commit history is kept:
  - `P2P-Crypto-Dashboard` (main @ 643ed57) → `apps/p2p-dashboard`
  - `CryptoSync-Pro` (main @ fde6aba) → `apps/chart-sync`
- Secret scan of the full imported history: no keys found. Both apps read `GEMINI_API_KEY`
  only from a local, gitignored env file.
- Safety defaults: paper trading by default, live trading behind an explicit flag,
  exchange keys only from env, trade-only keys (never withdrawal permission).

## Phases

### Phase 0 — Folder + import (done)
- [x] `~/Documents/workspace/trading-bot`, git repo, `.gitignore`, MIT `LICENSE`, `README.md`
- [x] Import both apps with history
- [x] Both apps build (`vite build`)

### Phase 1 — Publish + retire the old repos (done 2026-11-26)
- [x] Create public `Brandon-35/trading-bot`, push `main`
- [x] Disable GitHub Actions on it (`gh api -X PUT repos/Brandon-35/trading-bot/actions/permissions -F enabled=false`)
- [x] Back up each old repo: `git clone --mirror` → `git bundle create <name>.bundle --all` — evidence: `~/Documents/backups/repo-bundles/*-2026-11-26.bundle`, `git bundle verify` ok
- [x] Verify the new repo holds every old commit (`git log --oneline` per subtree path)
- [x] Delete `P2P-Crypto-Dashboard` and `CryptoSync-Pro` (`gh repo delete Brandon-35/<name> --yes`)

### Phase 2 — Monorepo tooling
- [ ] pnpm workspace (`apps/*`, `packages/*`), shared TypeScript config
- [ ] Remove AI Studio leftovers (banner, `metadata.json`, import maps) from both apps
- [ ] One `dev` command that runs both dashboards

### Phase 3 — Bot core (`bot/`)
Superseded 2026-11-27: the bot is an LLM-driven Python bot (owner decision), not a strategy/backtest package.
Spec, numbers and acceptance: `docs/plans/2026-11-27-llm-futures-bot.md`; tracking: issue #1.
- [x] `bot/trader/risk.py`: 2 % risk sizing, SL/RR checks, 6 % daily stop, 70 USDT full stop
- [x] `bot/trader/exchange.py`: Binance live/demo (exchange-side SL/TP) + paper simulator
- [x] `bot/trader/llm.py`: one OpenAI-compatible client for GLM, Kimi, OpenAI, Claude
- [ ] Paper arena (4 models) → demo re-check → live 100 USDT (milestones M1–M4 on #1)

### Phase 4 — Dashboards as bot features
- [ ] `chart-sync`: show bot entries/exits on the synced charts
- [ ] `p2p-dashboard`: generalise into a portfolio + bot PnL view fed by the engine

### Phase 5 — Open-source polish
- [ ] CONTRIBUTING, issue templates, security policy (how to report key leaks)
- [ ] Docs: quick start with paper trading in under 5 minutes

## Out of scope now

- Updating the `ideal` repo (Portfolio Hub) and the brandon-ta.com site.
