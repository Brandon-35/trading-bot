# LLM-driven Binance USDⓈ-M Futures bot, 24/7 on server-brandon-service

A small Python bot asks an LLM (GLM, Kimi, OpenAI or Claude through one OpenAI-compatible client)
for a trade decision on every closed 1h candle. Code then validates that decision, sizes the trade
from a fixed risk budget, places the entry with stop-loss and take-profit on Binance, and logs
everything. The LLM proposes; code owns money and risk. Capital starts at 100 USDT.

## Why
- **Who:** the owner, trading their own 100 USDT on Binance USDⓈ-M Futures.
- **Current behavior:** the repo has two React dashboards (`apps/chart-sync`, `apps/p2p-dashboard`) and no trading code; `packages/` holds only `.gitkeep`.
- **Desired behavior:** a bot that runs 24/7 in Docker, lets an LLM choose long/short/close/hold, and can never open a position without an exchange-side stop-loss.
- **Why now:** the owner chose LLM-as-trader (2026-11-27) and wants one page with every number decided before building.
- **Done when:** the Acceptance list below is ticked with evidence, ending with a live 100 USDT run that passed the paper gate.

## Current state (verified 2026-11-27)
- Repo `Brandon-35/trading-bot`, public, MIT, Actions disabled; `docs/PLAN.md` Phase 0–1 done; no Python code yet.
- `server-brandon-service` (Contabo 5.189.155.78) geolocates to **FR**; `GET https://fapi.binance.com/fapi/v1/ping` → 200 in 0.32–0.69 s; NTP synced; 4 vCPU, ~3.1 GB RAM available, 66 GB disk free; 29 containers already running; stacks live in `/opt/services/<name>/`.
- Binance USDⓈ-M fees (regular user): maker 0.02 %, taker 0.05 %; 10 % off with BNB in the futures wallet.
- Live `exchangeInfo` 2026-11-27: min notional BTCUSDT 50 (minQty 0.001 × 60,458 ≈ 60 USDT effective), ETHUSDT 20, SOLUSDT 5.
- Funding: BTC/ETH every 8 h, default 0.01 % per 8 h.
- Since 2025-12-09 conditional orders (STOP_MARKET, TAKE_PROFIT_MARKET) must go to `POST /fapi/v1/algoOrder`; the old endpoint returns -4120. ccxt routes `stopLossPrice` / `takeProfitPrice` there automatically (ccxt 4.5.94, 2026-11-23).
- Demo: `ccxt.binance(...).enable_demo_trading(True)` → `demo-fapi.binance.com`, key from demo.binance.com.
- Rate limits: 2,400 request weight/min per IP, 1,200 orders/min; a bot calling once per hour uses well under 1 %.
- LLM prices (vendor pages 2026-11-27), workload 1 call/h × ~6k in + 400 out tokens = 4.32M in + 0.29M out per month:

| Model | $/1M in | $/1M out | $/month @1h | $/month @15m |
|---|---|---|---|---|
| gpt-6-luna | 0.10 | 0.50 | 0.58 | 2.30 |
| claude-haiku-5-5 | 0.10 | 0.50 | 0.58 | 2.30 |
| glm-5.3-flash | 0.15 | 0.50 | 0.79 | 3.17 |
| glm-5.3 | 1.40 | 4.40 | 7.31 | 29.26 |
| kimi-k3.1-pro (3rd-party price) | 2.00 | 10.00 | 11.52 | 46.08 |
| claude-sonnet-5-5 / gpt-6.2-sol | 2.00 | 10.00 | 11.52 | 46.08 |
| claude-opus-5-5 | 4.00 | 20.00 | 23.04 | 92.16 |

- GLM Coding Plan and Kimi Code plan terms limit use to listed coding tools → the bot needs pay-as-you-go API keys.
- Anthropic's OpenAI-compatible endpoint accepts only `response_format: json_schema` with `strict: true`; `json_object` → 400.
- Alpha Arena season 1 (real money, crypto perps, 2025-10-18 → 11-03): Qwen3 Max +22.3 %, DeepSeek +4.9 %, Claude Sonnet 4.5 −42 %, Gemini 2.5 Pro −45.6 %, Grok −57.9 %, GPT-5 −58.7 %. Four of six lost money.

### Monte Carlo: 100 → 10,000 USDT (20,000 runs, 24 months, 30 trades/month, R:R 2, fees 0.09 R per trade, ruin = equity < 70 = the bot's full stop)

| Win rate | Risk/trade | P(reach 10k) | P(ruin) | Median after 24 mo |
|---|---|---|---|---|
| 35 % | 2 % | 0 % | 92.2 % | 65 |
| 40 % | 2 % | 0 % | 19.6 % | 288 |
| 40 % | 5 % | 9.3 % | 52.7 % | 69 |
| 45 % | 1 % | 0 % | 0 % | 533 |
| **45 %** | **2 %** | **6.4 %** | **1.0 %** | **2,855** |
| 45 % | 5 % | 82.6 % | 12.6 % | 127,742 |
| 50 % | 2 % | 87.7 % | 0.1 % | 24,905 |
| 45 % + flagship LLM 12 $/mo | 2 % | 1.1 % | 33.7 % | 573 |
| 50 % "all-in" 50 % risk | 50 % | 13.0 % | 99.8 % | 4 |

Fee assumption: 0.09 R per trade holds for a stop about 1.1 % away (taker in + out = 0.1 % of notional). A stop at the 0.5 × ATR floor (≈ 0.4 %) costs about 0.25 R, so the SL floor is set to max(0.5 × ATR, 0.8 %).

### How weak is the go-live gate? (simulated, 40 paper trades, R:R 2, fees 0.09 R)
| True win rate | One model passes PF ≥ 1.2 | Best of 4 passes | Best of 4 + passes a fresh 20-trade demo with PF ≥ 1.0 |
|---|---|---|---|
| 33 % (no edge, loses after fees) | 14.3 % | 46.7 % | 15.4 % |
| 36 % | 24.1 % | 67.5 % | 29.6 % |
| 40 % | 43.9 % | 89.7 % | 52.4 % |

So the arena alone lets a no-edge model through about half the time; the fresh demo re-check cuts that to about 15 %. The remaining risk is bounded by the −30 % full stop (≤ 30 USDT).

Reading: the result depends almost entirely on the win rate the LLM actually achieves, which nobody knows yet. That is why it must be measured on paper first. A 12 $/month model eats 12 % of a 100 $ account per month and turns a winning system into a 34 % ruin risk. The model ignores slippage and assumes a stable edge, so real numbers will be worse.

## Scope
- In: Python bot (ccxt + openai SDK), risk engine, paper simulator for a 4-model arena, demo plumbing test, live mode, SQLite log, Telegram alerts, Docker deploy on server-brandon-service, unit tests.
- Out: dashboard integration (Phase 4 of `docs/PLAN.md`), pnpm monorepo (Phase 2), backtesting LLMs on historical data (look-ahead leakage makes it meaningless), hedge mode, more than one exchange, web UI, a Telegram command interface (stop = `docker compose stop`).
- Ordering: signed-call check from the server → risk engine + tests → LLM client → paper arena (≥ 40 trades per model, about 6 weeks) → demo re-check (≥ 20 fresh trades) → owner's second go → live 100 USDT.
- Smallest version: one process, one loop on the 1h close, one prompt file, one SQLite file.
- Failure mode & rollback: a bug can open a position without protection or oversize it. The defenses are: exchange-side SL placed right after entry, with a market close if SL placement fails; startup reconciliation from the exchange; hard caps in code; daily and total stop. Rollback = `docker compose stop` + close positions in the Binance app.

## Options
| Option | Change | Cost | Risk |
|---|---|---|---|
| A. Own small Python bot (recommended) | ~600 lines: loop, risk, llm, exchange, paper, tests | 2–3 days build | Owned code, but small and fully tested |
| B. Fork NOFX (Go, 13k★) | Already does LLM → Binance perps | Learn a large Go codebase | AGPL-3.0 infects the MIT repo; referral links and paid data routes |
| C. freqtrade + LLM inside a strategy | Mature engine, backtest, Telegram | Fight the framework: it is built for indicator strategies, not one LLM call per candle across symbols | Heavy; LLM backtests are leaky anyway |

## Plan
### Fixed decisions (mechanical, no need to choose)
- Python 3.12, `ccxt` ≥ 4.5.94, `openai` SDK, `pydantic` for the decision schema, `pytest`. No LiteLLM, no framework.
- Layout: `bot/` at repo root (`bot/trader/*.py`, `bot/prompts/system.md`, `bot/tests/`, `bot/Dockerfile`, `bot/compose.yml`, `bot/.env.example`).
- Exchange settings per symbol: one-way mode, isolated margin, leverage = cap. Exchange state is the source of truth; reconcile positions and open algo orders on every start and every cycle.
- Each entry is a market order, then a STOP_MARKET and a TAKE_PROFIT_MARKET with `closePosition=true` via ccxt `stopLossPrice` / `takeProfitPrice`. If either protective order fails, close the position at market and alert.
- LLM input, computed by code: 4h/1h/15m OHLCV (last 50 each), EMA20/50, RSI14, ATR14, funding, open interest change, open positions, equity, today's PnL. One call per hour covers all symbols. Temperature 0, timeout 60 s, 2 retries; any error or invalid JSON → `hold`.
- LLM output (strict JSON schema): `[{symbol, action: long|short|close|hold, stop_loss, take_profit, confidence 0–1, reason}]`.
- Code rejects a decision when: SL is missing or on the wrong side; SL distance is below max(0.5 × ATR(1h), 0.8 %) or above 3 × ATR(1h); R:R < 1.5; confidence < 0.6; or the symbol is not allowed.
- Before any new entry or `close`, cancel every open algo order for that symbol, so a leftover `closePosition` order can never fire on the next position.
- Sizing: `qty = risk_usdt / |entry − SL|`, rounded down to the lot step; skip if notional < min notional or the margin needed exceeds free margin.
- Limits: max 2 open positions; total open risk ≤ 2 × risk per trade; daily loss ≥ 6 % → pause until 00:00 UTC; equity < 70 USDT (−30 %) → full stop until manual restart.
- Storage: SQLite file in a Docker volume (decisions, prompts, orders, fills, equity snapshots). Logs never contain keys.
- Deploy: `/opt/services/trading-bot/` on server-brandon-service, `restart: unless-stopped`, `TZ=Asia/Ho_Chi_Minh`, no published port, no Caddy. Deploy by hand (rsync + `docker compose up -d --build`); GitHub Actions stays off.
- Secrets: `.env` on the server, `chmod 600`, never committed. The live Binance key has Futures trading on, withdrawals off, and an IP whitelist of 5.189.155.78. The demo key is separate.
- Telegram alerts: every open, close and rejection, plus errors and the daily-stop trigger, and a daily 08:00 summary.

### Phase 0a — signed call from the server (before any build)
- With a read-only live key whitelisted to 5.189.155.78, run a signed `fetch_balance` on `binanceusdm` from server-brandon-service.
- Verify: balance JSON returned, no 451/403. If it fails, the host changes before anything else is built.
### Phase 0 — risk engine + tests
- `bot/trader/risk.py`: sizing, validation, limits as pure functions; `bot/tests/test_risk.py`.
- Verify: `cd bot && pytest -q` green.
### Phase 1 — LLM client + prompt
- `bot/trader/llm.py`: one OpenAI client; `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from env; pydantic validates every reply.
- Assumption to verify in AC2: strict `json_schema` works on OpenAI and Anthropic's compat endpoint (Anthropic accepts only that); GLM and Kimi `json_schema` support is unverified, so fall back to `json_object` + pydantic there. Anthropic documents its OpenAI endpoint as test-only (no prompt caching, thinking on by default, temperature 0 not guaranteed); if it misbehaves, Claude gets a native `anthropic` SDK branch of about 20 lines.
- Verify: `python -m trader.llm --dry` returns a valid decision from each provider.
### Phase 2 — paper arena (≥ 40 trades per model, minimum 14 days, about 6 weeks at 1h)
- `bot/trader/paper.py`: simulated fills at the next 1m open + 0.05 % fee + 0.02 % slippage; SL/TP hit checked on 1m candles; funding applied every 8 h.
- 4 containers (one per model), same candles, same rules, 100 USDT virtual each.
- Verify: a table per model of trades, win rate, profit factor, max drawdown and LLM cost. API cost for the whole arena ≈ 20 USD (≈ 13.5 USD/month for the 4 models, Kimi is 11.5 of that).
### Phase 3 — demo re-check (arena winner, ≥ 20 fresh trades)
- `enable_demo_trading(True)`; real order path including algo SL/TP, failure path, orphan-order cleanup, restart reconciliation; doubles as the out-of-sample check (PF ≥ 1.0).
### Phase 4 — live 100 USDT
- Only after the go-live gate passes AND the owner gives a second, explicit go in chat. Approving this page does not authorize live trading. Same code; `MODE=live`.
- Anti-pattern: never let the LLM set quantity or leverage; never place an entry before checking that SL validation passed.

## Risks & rollback
- LLM has no edge (Alpha Arena: 4 of 6 lost) → the paper gate plus the demo re-check block it about 85 % of the time; if one slips through, the −30 % full stop caps the loss at 30 USDT. API cost for the arena ≈ 20 USD.
- Unprotected position (SL order rejected, crash between entry and SL) → market-close on SL failure; reconciliation each cycle adds a missing SL or closes.
- Server down while a position is open → the SL/TP live on Binance, not in the bot.
- API key leak → no withdrawal permission plus an IP whitelist means a thief can only trade from that IP; rotate the key.
- Binance blocks the server region (US-style 451) → FR verified for public endpoints only; the signed call is Phase 0a, before any build.
- LLM API cost → cheap tier only for live (≤ 2 % of capital/month); cost tracked per call.
- Binance API change (like the 2025-12-09 algo-order move) → pin ccxt; alert on any order error.
- Separate, pre-existing: `apps/p2p-dashboard/constants.ts` publishes real P2P trade history in this public repo (not touched by this plan).

## Acceptance
<!-- Tick an item only with proof: replace the placeholder with `<command → decisive output line | screenshot path | URL>`; a tick without evidence counts as open. -->
Build acceptance (one build session):
- [x] AC1 — signed `fetch_balance` from server-brandon-service with an IP-whitelisted key works; the key shows withdrawals disabled — evidence: `docker run … python -m trader.key_check` on server-brandon-service → `PASS signed fetch_balance` + apiRestrictions `ipRestrict True, enableWithdrawals False, enableFutures True`, spot/margin/transfer all False (2026-11-27)
- [x] AC2 — risk unit tests cover sizing, lot rounding, min-notional skip, SL floor/ceiling, RR, daily stop, total stop — evidence: `cd bot && uv run pytest -q` → `25 passed` (tests/test_risk.py 9 cases incl. min notional, margin cap, halts; Limits refuse risk > 2 % / leverage > 5)
- [ ] AC3 — each of the 4 providers returns a pydantic-valid decision from the real API (schema mode recorded per provider) — evidence: <fill when ticked>
- [x] AC4 — invalid LLM output (bad JSON, no SL, SL wrong side, RR 1.0) results in no order — evidence: tests/test_bot.py `test_bad_entries_place_no_order` (5 cases, broker.calls == []) + `test_llm_garbage_means_hold` → passed; live smoke on server with a bad key: `llm_call {"error": "AuthenticationError 401"}`, no order
- [ ] AC5 — on demo, an entry results in an open position plus SL and TP visible in `openAlgoOrders`; when SL fills the TP is gone, and the reverse — evidence: <fill when ticked>
- [ ] AC6 — forced SL placement failure on demo closes the position at market and sends an alert — evidence: <fill when ticked>
- [ ] AC7 — after a container kill with an open position, restart reconciles the position and its SL without a duplicate entry — evidence: <fill when ticked>
- [ ] AC8 — security pass: no secret in git history, image or logs; `.env` mode 600 on the server — evidence: <fill when ticked>
- [ ] AC9 — the paper arena container set is running on the server and writes decisions to SQLite — evidence: <fill when ticked>
- [ ] AC10 — all verify commands are green — evidence: <fill when ticked>

Operational milestones (weeks later, tracked on the GitHub issue, not ticked in the build session):
- M1 — arena reached ≥ 40 trades per model; the results table is added to this plan.
- M2 — the winner passed the go-live gate (D7) and ≥ 20 fresh demo trades with PF ≥ 1.0.
- M3 — the owner gave a second, explicit go for live trading in chat.
- M4 — live: 72 h with no restart loop and a daily Telegram summary; first live trade has its SL on the exchange.

## Needs
- Superseded 2026-11-27 (owner): no demo key; order path is checked on live with ~12 USDT. Was: BINANCE_DEMO_KEY — demo.binance.com API key + secret (Phase 3; used by `python -m trader.demo_check` for AC5–AC7)
- NEEDS: BINANCE_LIVE_KEY — live key: Futures on, withdrawals off, IP whitelist 5.189.155.78; read-only at first for Phase 0a, Futures trading switched on only at Phase 4
- NEEDS: LLM_KEYS — pay-as-you-go keys for z.ai (GLM), platform.moonshot.ai (Kimi), OpenAI, Anthropic (Phase 1; AC3 via `python -m trader.llm --dry`; local ~/.config/anthropic key returns 401)
- Superseded 2026-11-27 (owner): Discord instead of Telegram.
- NEEDS: DISCORD_WEBHOOK_URL — channel webhook for alerts (`trader/notify.py`)
- NEEDS: FUNDING — 100 USDT moved into the USDⓈ-M futures wallet (Phase 4)

## Files
| File | Change | churn/90d |
|---|---|---|
| `bot/trader/{main,risk,llm,exchange,paper,store,notify}.py` | new | 0 |
| `bot/prompts/system.md` | new | 0 |
| `bot/tests/test_*.py` | new | 0 |
| `bot/{Dockerfile,compose.yml,.env.example,pyproject.toml}` | new | 0 |
| `docs/PLAN.md` | Phase 3 rewritten to point at this plan | 2 |
| `README.md` | layout row for `bot/` + run section | 2 |

## Gate
```json
{
  "verdict": {
    "vi": "LỚN · H3 tiền thật · H4 secrets · S5 service 24/7",
    "en": "LARGE · H3 real money · H4 secrets · S5 24/7 service"
  },
  "triggers": [
    "H3",
    "H4",
    "S2",
    "S3",
    "S5"
  ],
  "tldr": {
    "vi": "Bot Python chạy 24/7 trên server (Pháp): mỗi nến 1h hỏi LLM (GLM/Kimi/GPT/Claude) nên long/short/đóng/đứng ngoài; code tự tính khối lượng theo rủi ro 2%/lệnh, đặt SL+TP ngay trên Binance, dừng khi lỗ 6%/ngày hoặc −30% tổng. Trước khi dùng 100 USDT thật: 4 model thi đấu trên giấy tới khi đủ 40 lệnh/model (~6 tuần, ~20$ API), model thắng phải qua thêm 20 lệnh demo, rồi bạn nói 'go' lần 2.",
    "en": "Python bot, 24/7 on the FR server: on every 1h close an LLM picks long/short/close/hold; code sizes at 2% risk, places SL+TP on Binance, stops at −6%/day or −30% total. Before real money: 4 models paper-trade for 14 days; only a model that passes the gate trades the 100 USDT."
  },
  "flow": {
    "before": [
      "Repo chỉ có 2 dashboard React",
      "Không có code đặt lệnh"
    ],
    "after": [
      "Nến 1h đóng → code tính chỉ báo",
      "LLM trả JSON quyết định",
      "Code kiểm tra SL/RR/ATR + tính khối lượng",
      "Lệnh market + SL + TP trên Binance",
      "Ghi SQLite + báo Telegram",
      "Lỗ 6%/ngày → nghỉ; −30% → dừng hẳn"
    ]
  },
  "verify": [
    "cd bot && pytest -q",
    "docker compose -f bot/compose.yml config -q",
    "ssh server-brandon-service 'docker compose -f /opt/services/trading-bot/compose.yml ps'"
  ],
  "files": [
    "bot/**",
    "docs/PLAN.md",
    "README.md"
  ],
  "env_files": [
    "bot/.env.example"
  ],
  "target": "main",
  "task": "Brandon-35/trading-bot#1",
  "read": {
    "Why": {
      "h": "Vì sao",
      "md": "- **Ai:** bạn, trade 100 USDT của chính mình trên Binance Futures (USDⓈ-M).\n- **Đang là:** repo chỉ có 2 dashboard React, `packages/` trống, chưa có dòng code đặt lệnh nào.\n- **Nên là:** bot chạy 24/7 trong Docker, LLM chọn long/short/đóng/đứng ngoài, và **không bao giờ** có vị thế nào thiếu stop-loss trên sàn.\n- **Vì sao bây giờ:** bạn đã chốt dùng LLM làm trader (27/11) và muốn một trang có đủ số liệu để chốt.\n- **Xong khi:** mọi mục Nghiệm thu có bằng chứng, kết thúc bằng đợt chạy 100 USDT thật sau khi qua vòng thử trên giấy."
    },
    "Current state (verified 2026-11-27)": {
      "h": "Hiện trạng (đã kiểm tra 27/11/2026)",
      "md": "**Server & sàn**\n- `server-brandon-service` đặt ở **Pháp**, gọi API Binance Futures → 200, độ trễ 0.3–0.7 s, giờ hệ thống đồng bộ; còn ~3.1 GB RAM, 66 GB đĩa.\n- Phí Futures: maker 0.02%, taker 0.05% (giảm 10% nếu trả bằng BNB).\n- Lệnh tối thiểu: BTC ≈ 60 USDT, ETH 20, SOL 5.\n- Funding BTC/ETH mỗi 8h, mặc định 0.01%.\n- Từ 09/12/2025 lệnh SL/TP phải đi qua endpoint `algoOrder` mới; ccxt 4.5.94 đã tự xử lý.\n- Có môi trường **demo** (`demo-fapi`) để thử lệnh thật bằng tiền ảo.\n\n**Giá LLM (1 lần gọi/giờ ≈ 6k token vào + 400 ra)**\n\n| Model | $/tháng @1h | $/tháng @15m |\n|---|---|---|\n| gpt-6-luna | 0.58 | 2.30 |\n| claude-haiku-5-5 | 0.58 | 2.30 |\n| glm-5.3-flash | 0.79 | 3.17 |\n| glm-5.3 | 7.31 | 29.26 |\n| kimi-k3.1-pro | 11.52 | 46.08 |\n| claude-sonnet-5-5 / gpt-6.2-sol | 11.52 | 46.08 |\n| claude-opus-5-5 | 23.04 | 92.16 |\n\n- Gói Coding Plan của GLM/Kimi **cấm** dùng cho bot → cần key trả theo lượt.\n- Alpha Arena mùa 1 (tiền thật, LLM trade crypto): Qwen +22%, DeepSeek +5%, Claude Sonnet 4.5 −42%, Gemini −46%, Grok −58%, GPT-5 −59%. **4/6 model lỗ.**\n\n**Mô phỏng 100 → 10.000 USDT** (20.000 lần chạy, 24 tháng, 30 lệnh/tháng, R:R 1:2, đã trừ phí; \"cháy\" = vốn < 70 USDT, đúng mức bot dừng hẳn)\n\n| Tỉ lệ thắng | Rủi ro/lệnh | Xác suất đạt 10k | Xác suất cháy | Trung vị sau 24 tháng |\n|---|---|---|---|---|\n| 35% | 2% | 0% | 92% | 65 |\n| 40% | 2% | 0% | 20% | 288 |\n| 40% | 5% | 9% | 53% | 69 |\n| 45% | 1% | 0% | 0% | 533 |\n| **45%** | **2%** | **6.4%** | **1%** | **2.855** |\n| 45% | 5% | 83% | 13% | 127.742 |\n| 50% | 2% | 88% | 0.1% | 24.905 |\n| 45% + LLM đắt 12$/tháng | 2% | 1.1% | 34% | 573 |\n| All-in 50%/lệnh | 50% | 13% | **99.8%** | 4 |\n\n> [!warning] Kết quả gần như chỉ phụ thuộc vào tỉ lệ thắng thật của LLM, mà chưa ai biết. Vì vậy phải đo trên giấy trước. Model đắt 12$/tháng ăn 12% tài khoản mỗi tháng → hệ thống đang thắng cũng thành 34% cháy. Mô phỏng chưa tính trượt giá nên thực tế sẽ xấu hơn.\n\n- Phí 0.09R/lệnh chỉ đúng khi SL cách ~1.1%. SL sát (0.4%) thì phí ≈ 0.25R → SL tối thiểu đặt = max(0.5×ATR, 0.8%).\n\n**Ngưỡng go-live lọc được bao nhiêu?** (mô phỏng 40 lệnh giấy)\n\n| Tỉ lệ thắng thật | 1 model lọt PF ≥ 1.2 | Model tốt nhất trong 4 lọt | Tốt nhất trong 4 + qua thêm 20 lệnh demo mới PF ≥ 1.0 |\n|---|---|---|---|\n| 33% (không có lợi thế, lỗ sau phí) | 14% | 47% | 15% |\n| 36% | 24% | 68% | 30% |\n| 40% | 44% | 90% | 52% |\n\n> [!warning] Chỉ thi đấu giấy thì model 'ăn may' lọt tới ~50%. Thêm vòng demo mới giảm còn ~15%. Phần rủi ro còn lại bị chặn bởi mức dừng −30% (tối đa mất 30 USDT)."
    },
    "Scope": {
      "h": "Phạm vi",
      "md": "- **Làm:** bot Python (ccxt + openai SDK), bộ quản lý rủi ro, mô phỏng giấy cho 4 model thi đấu, thử lệnh trên demo, chạy thật, log SQLite, báo Telegram, Docker trên server, unit test.\n- **Không làm:** nối dashboard, monorepo pnpm, backtest LLM trên dữ liệu cũ (LLM đã 'thấy' quá khứ → vô nghĩa), hedge mode, sàn khác, web UI, lệnh điều khiển qua Telegram (dừng = `docker compose stop`).\n- **Thứ tự:** kiểm tra lệnh có ký từ server → rủi ro + test → LLM → thi đấu giấy (≥ 40 lệnh/model, ~6 tuần) → demo kiểm tra lại (≥ 20 lệnh) → bạn 'go' lần 2 → 100 USDT thật.\n- **Bản nhỏ nhất:** 1 tiến trình, 1 vòng lặp theo nến 1h, 1 file prompt, 1 file SQLite.\n- **Hỏng thì sao:** lỗi có thể mở lệnh thiếu SL hoặc quá to → SL đặt trên sàn ngay sau lệnh vào, đặt SL lỗi thì đóng lệnh ngay; mỗi lần khởi động đối chiếu lại với sàn; giới hạn cứng trong code. Gỡ: `docker compose stop` + đóng lệnh trong app Binance."
    },
    "Options": {
      "h": "Các cách làm",
      "md": "| Cách | Sửa gì | Chi phí | Rủi ro |\n|---|---|---|---|\n| **A. Tự viết bot Python nhỏ (đề xuất)** | ~600 dòng: vòng lặp, rủi ro, LLM, sàn, giấy, test | 2–3 ngày | Code của mình, nhỏ, test đủ |\n| B. Fork NOFX (Go, 13k★) | Đã có LLM → Binance perp | Phải học codebase Go lớn | AGPL-3.0 lây sang repo MIT; có link referral + dữ liệu trả phí |\n| C. freqtrade + LLM trong strategy | Engine trưởng thành | Phải 'đánh nhau' với framework vốn làm cho chỉ báo, không phải 1 lần gọi LLM/nến cho nhiều coin | Nặng; backtest LLM vẫn sai |"
    },
    "Plan": {
      "h": "Kế hoạch",
      "md": "**Đã chốt sẵn (không cần bạn chọn)**\n- Python 3.12, `ccxt` ≥ 4.5.94, `openai` SDK, `pydantic`, `pytest`. Không framework.\n- Mỗi coin: one-way, **isolated**, đòn bẩy = trần.\n- Vào lệnh market → đặt ngay STOP_MARKET + TAKE_PROFIT_MARKET `closePosition=true`. Đặt SL/TP lỗi → đóng lệnh ngay + báo.\n- Dữ liệu cho LLM do code tính: nến 4h/1h/15m (50 nến), EMA20/50, RSI14, ATR14, funding, OI, vị thế, vốn, PnL hôm nay. **1 lần gọi/giờ cho tất cả coin**. Lỗi/JSON sai → đứng ngoài.\n- Code **từ chối** quyết định khi: thiếu SL / SL sai phía / SL gần hơn max(0.5×ATR, 0.8%) hoặc xa hơn 3×ATR / R:R < 1.5 / confidence < 0.6.\n- Trước mỗi lệnh vào mới hoặc lệnh đóng: huỷ mọi lệnh SL/TP cũ của coin đó, để lệnh mồ côi không bắn nhầm vào vị thế sau.\n- JSON: OpenAI + Claude dùng `json_schema` strict; GLM/Kimi chưa xác minh → dùng `json_object` + pydantic kiểm tra. Endpoint OpenAI của Anthropic chỉ dành cho thử nghiệm → nếu chập chờn thì Claude dùng SDK `anthropic` riêng (~20 dòng).\n- Khối lượng = tiền rủi ro ÷ khoảng cách SL; nhỏ hơn lệnh tối thiểu → bỏ qua.\n- Tối đa **2 vị thế** cùng lúc; lỗ **6%/ngày** → nghỉ tới 07:00 sáng hôm sau (00:00 UTC); vốn < **70 USDT** → dừng hẳn, bạn tự bật lại.\n- Lưu SQLite trong volume Docker; log không bao giờ chứa key.\n- Deploy `/opt/services/trading-bot/`, tự khởi động lại, không mở cổng; deploy tay (Actions tắt).\n- Key thật: bật Futures, **tắt rút tiền**, **khoá IP 5.189.155.78**. Key demo riêng.\n- Telegram: báo mỗi lệnh vào/ra/bị từ chối, lỗi, chạm dừng ngày, tóm tắt 08:00 hằng ngày.\n\n**Các giai đoạn**\n0. **Kiểm tra lệnh có ký từ server** (key chỉ đọc, khoá IP) — trước khi viết code. Lỗi → đổi server trước.\n1. Rủi ro + test.\n2. LLM client + prompt.\n3. **Thi đấu giấy tới khi mỗi model có ≥ 40 lệnh** (tối thiểu 14 ngày, ~6 tuần ở khung 1h): 4 model, cùng nến, cùng luật, mỗi model 100 USDT ảo; khớp lệnh mô phỏng theo nến 1m + phí 0.05% + trượt 0.02% + funding. Tiền API cả vòng ≈ **20$**.\n4. **Demo kiểm tra lại** với model thắng: ≥ 20 lệnh mới, PF ≥ 1.0; đồng thời thử đường đặt lệnh, lỗi SL, lệnh mồ côi, khởi động lại.\n5. **100 USDT thật** — chỉ khi qua ngưỡng **và bạn nói 'go' lần thứ hai trong chat**. Duyệt trang này **chưa** cho phép trade tiền thật."
    },
    "Risks & rollback": {
      "h": "Rủi ro & cách gỡ",
      "md": "- **LLM không có lợi thế** (Alpha Arena 4/6 lỗ) → vòng giấy + demo chặn được ~85%; nếu lọt, mức dừng −30% giới hạn lỗ ở 30 USDT. Tiền API vòng giấy ≈ 20$.\n- **Vị thế không có SL** (SL bị từ chối, crash giữa chừng) → đóng ngay khi SL lỗi; mỗi vòng kiểm tra lại, thiếu SL thì đặt bù hoặc đóng.\n- **Server sập khi đang có lệnh** → SL/TP nằm trên Binance, không phụ thuộc bot.\n- **Lộ key** → không có quyền rút + khoá IP ⇒ kẻ trộm chỉ trade được từ đúng IP server; đổi key.\n- **Binance chặn vùng server** → Pháp mới chỉ gọi được API công khai; lệnh có ký được kiểm tra ở bước 0, trước khi viết code.\n- **Tiền API LLM** → chạy thật chỉ dùng model rẻ (≤ 2% vốn/tháng), ghi chi phí từng lần gọi.\n- **Binance đổi API** (như vụ algoOrder 12/2025) → ghim phiên bản ccxt, báo mọi lỗi lệnh.\n- Riêng, có sẵn từ trước: `apps/p2p-dashboard/constants.ts` đang công khai lịch sử P2P thật của bạn (kế hoạch này không đụng)."
    },
    "Acceptance": {
      "h": "Nghiệm thu",
      "md": "**Nghiệm thu khi build (1 phiên làm):**\n- AC1 — từ server gọi `fetch_balance` có ký bằng key khoá IP → OK; key hiển thị tắt rút tiền\n- AC2 — test rủi ro: khối lượng, làm tròn lot, bỏ qua dưới mức tối thiểu, SL sàn/trần, R:R, dừng ngày, dừng tổng\n- AC3 — cả 4 nhà cung cấp trả JSON hợp lệ (pydantic) từ API thật, ghi lại chế độ schema của từng hãng\n- AC4 — LLM trả sai (JSON hỏng, thiếu SL, SL sai phía, R:R 1.0) → không có lệnh nào\n- AC5 — trên demo: vào lệnh → có vị thế + SL + TP trong `openAlgoOrders`; SL khớp thì TP biến mất và ngược lại\n- AC6 — ép SL lỗi trên demo → lệnh bị đóng market + có báo\n- AC7 — kill container khi đang có lệnh, bật lại → nhận lại vị thế + SL, không vào trùng\n- AC8 — bảo mật: không có secret trong git, image, log; `.env` quyền 600\n- AC9 — cụm container thi đấu giấy chạy trên server và ghi quyết định vào SQLite\n- AC10 — mọi lệnh verify xanh\n\n**Mốc vận hành (vài tuần sau, theo dõi trên GitHub issue):**\n- M1 — mỗi model đủ ≥ 40 lệnh giấy; bảng kết quả ghi vào plan\n- M2 — model thắng qua ngưỡng go-live (D7) + ≥ 20 lệnh demo mới với PF ≥ 1.0\n- M3 — **bạn nói 'go' lần 2** cho tiền thật\n- M4 — chạy thật 72h không lỗi, có tóm tắt Telegram hằng ngày; lệnh thật đầu tiên có SL trên sàn"
    },
    "Needs": {
      "h": "Cần bạn cung cấp (khi tới bước đó)",
      "md": "- **Key demo Binance** (demo.binance.com) — giai đoạn 4\n- **Key thật Binance**: tắt rút tiền, khoá IP `5.189.155.78`; lúc đầu **chỉ đọc** (bước 0), tới giai đoạn 5 mới bật Futures trading\n- **Key API LLM trả theo lượt**: z.ai (GLM), platform.moonshot.ai (Kimi), OpenAI, Anthropic — giai đoạn 2\n- **Telegram**: token bot từ @BotFather + chat id — giai đoạn 3\n- **100 USDT** chuyển vào ví USDⓈ-M Futures — giai đoạn 5"
    },
    "Files": {
      "h": "File",
      "md": "| File | Thay đổi |\n|---|---|\n| `bot/trader/{main,risk,llm,exchange,paper,store,notify}.py` | mới |\n| `bot/prompts/system.md` | mới |\n| `bot/tests/test_*.py` | mới |\n| `bot/{Dockerfile,compose.yml,.env.example,pyproject.toml}` | mới |\n| `docs/PLAN.md` | Phase 3 trỏ sang plan này |\n| `README.md` | thêm dòng `bot/` + cách chạy |"
    }
  },
  "skills": [
    {
      "domain": "plan",
      "skill": "cc:gate",
      "phase": "P3"
    },
    {
      "domain": "money, secrets",
      "skill": "ecc:security-review",
      "phase": "build + P6a"
    },
    {
      "domain": "LLM trading safety",
      "skill": "ecc:llm-trading-agent-security",
      "phase": "build"
    },
    {
      "domain": "new code",
      "skill": "superpowers:test-driven-development",
      "phase": "build"
    },
    {
      "domain": "docker deploy",
      "skill": "ecc:docker-patterns",
      "phase": "build"
    },
    {
      "domain": "done",
      "skill": "superpowers:verification-before-completion",
      "phase": "P6a"
    }
  ],
  "decisions": [
    {
      "id": "C1",
      "kind": "challenge",
      "title": {
        "vi": "Mục tiêu 100$ → 10.000$",
        "en": "Goal 100$ → 10,000$"
      },
      "you_said": "Mục tiêu kiếm từ 100$ lên 10.000$.",
      "we_recommend": "Giữ 10.000$ làm đích xa, nhưng KPI từng giai đoạn là: (1) qua vòng giấy, (2) 30 ngày thật có profit factor > 1.2 sau phí, (3) mới nạp thêm vốn. Không tăng rủi ro/lệnh để 'đuổi' mục tiêu.",
      "why": "Mô phỏng (cháy = vốn < 70): thắng 45%, rủi ro 2% → 1% cháy nhưng chỉ 6% đạt 10k trong 24 tháng; rủi ro 5% → 83% đạt nhưng nếu tỉ lệ thắng thật chỉ 40% thì 53% cháy. All-in 50% → 99.8% cháy. Tỉ lệ thắng thật của LLM chưa biết.",
      "missing": "Nếu LLM thật sự thắng ≥ 50% thì rủi ro 2% vẫn đạt 10k với xác suất ~88% trong ~20 tháng, nên không cần mạo hiểm hơn.",
      "cost_if_wrong": "Chọn rủi ro cao khi chưa đo được lợi thế → mất phần lớn 100$ trong vài tuần."
    },
    {
      "id": "D1",
      "kind": "taste",
      "title": {
        "vi": "Khung thời gian ra quyết định",
        "en": "Decision timeframe"
      },
      "recommended": "h1",
      "question": {
        "vi": "Bot hỏi LLM sau mỗi nến bao lâu?",
        "en": "How often does the bot ask the LLM?"
      },
      "options": [
        {
          "id": "h1",
          "label": {
            "vi": "1 giờ",
            "en": "1 hour"
          },
          "note": {
            "vi": "~30 lệnh/tháng, phí và nhiễu vừa phải, LLM rẻ ~0.6–0.8$/tháng",
            "en": "~30 trades/month, moderate fees and noise"
          }
        },
        {
          "id": "m15",
          "label": {
            "vi": "15 phút",
            "en": "15 minutes"
          },
          "note": {
            "vi": "Nhiều lệnh hơn → phí ăn nhiều hơn, nhiễu hơn, LLM tốn ×4",
            "en": "More trades, more fees and noise, LLM cost ×4"
          }
        },
        {
          "id": "h4",
          "label": {
            "vi": "4 giờ",
            "en": "4 hours"
          },
          "note": {
            "vi": "Ít lệnh (~8/tháng) → 14 ngày giấy không đủ mẫu để đánh giá",
            "en": "Too few trades to judge in 14 days"
          }
        }
      ]
    },
    {
      "id": "D2",
      "kind": "taste",
      "title": {
        "vi": "Coin được trade",
        "en": "Symbols"
      },
      "recommended": "bes",
      "question": {
        "vi": "LLM được phép trade những cặp nào?",
        "en": "Which pairs may the LLM trade?"
      },
      "options": [
        {
          "id": "bes",
          "label": {
            "vi": "BTC + ETH + SOL",
            "en": "BTC + ETH + SOL"
          },
          "note": {
            "vi": "Thanh khoản sâu, đủ cơ hội; BTC cần lệnh ≥ 60 USDT nên đôi khi bị bỏ qua khi SL xa",
            "en": "Deep liquidity; BTC min 60 USDT sometimes skipped"
          }
        },
        {
          "id": "be",
          "label": {
            "vi": "Chỉ BTC + ETH",
            "en": "BTC + ETH only"
          },
          "note": {
            "vi": "An toàn hơn nhưng ít lệnh, BTC hay bị vướng lệnh tối thiểu",
            "en": "Fewer trades"
          }
        },
        {
          "id": "top10",
          "label": {
            "vi": "Top 10 volume, LLM tự chọn",
            "en": "Top 10 by volume"
          },
          "note": {
            "vi": "Nhiều cơ hội nhưng altcoin biến động mạnh, prompt dài hơn → tốn hơn",
            "en": "More volatile, longer prompts"
          }
        }
      ]
    },
    {
      "id": "D3",
      "kind": "taste",
      "title": {
        "vi": "Rủi ro mỗi lệnh",
        "en": "Risk per trade"
      },
      "recommended": "r2",
      "question": {
        "vi": "Mỗi lệnh chấp nhận mất tối đa bao nhiêu % vốn nếu chạm SL?",
        "en": "Max % of equity lost if SL is hit?"
      },
      "options": [
        {
          "id": "r2",
          "label": {
            "vi": "2% (≈2$ với vốn 100$)",
            "en": "2%"
          },
          "note": {
            "vi": "Thắng 45% → 1% cháy, trung vị 2.855$ sau 24 tháng; thắng 40% → 20% cháy",
            "en": "45% WR → 0% ruin"
          }
        },
        {
          "id": "r1",
          "label": {
            "vi": "1%",
            "en": "1%"
          },
          "note": {
            "vi": "Rất an toàn nhưng 24 tháng gần như không thể tới 10k",
            "en": "Very safe, slow"
          }
        },
        {
          "id": "r5",
          "label": {
            "vi": "5%",
            "en": "5%"
          },
          "note": {
            "vi": "Thắng 40% → 53% cháy; thắng 45% → 13% cháy. Chỉ cân nhắc sau khi đã đo được lợi thế",
            "en": "35% ruin at 40% WR"
          }
        }
      ]
    },
    {
      "id": "D4",
      "kind": "taste",
      "title": {
        "vi": "Cách chọn model",
        "en": "Model selection"
      },
      "recommended": "arena",
      "question": {
        "vi": "Cho 4 model thi đấu trên giấy, hay chọn luôn 1 model?",
        "en": "Paper arena of 4 models, or pick one?"
      },
      "options": [
        {
          "id": "arena",
          "label": {
            "vi": "Thi đấu giấy (≥ 40 lệnh/model, ~6 tuần): gpt-6-luna, claude-haiku-5-5, glm-5.3-flash, kimi-k3.1-pro",
            "en": "14-day paper arena of 4 models"
          },
          "note": {
            "vi": "Mỗi hãng 1 model, tổng ~20$ API; chọn theo số liệu thật. Model tốt nhất trong 4 dễ 'ăn may' hơn → bắt buộc qua thêm vòng demo",
            "en": "~7$ API total; pick by data"
          }
        },
        {
          "id": "single",
          "label": {
            "vi": "Chọn 1 model, chạy giấy luôn",
            "en": "One model on paper"
          },
          "note": {
            "vi": "Ít code hơn (~80 dòng), nhưng không biết model khác có tốt hơn không",
            "en": "Less code, no comparison"
          }
        }
      ]
    },
    {
      "id": "D5",
      "kind": "taste",
      "when": {
        "D4": "single"
      },
      "title": {
        "vi": "Model duy nhất",
        "en": "The single model"
      },
      "recommended": "haiku",
      "options": [
        {
          "id": "haiku",
          "label": {
            "vi": "claude-haiku-5-5 (0.58$/tháng)",
            "en": "claude-haiku-5-5"
          },
          "note": {
            "vi": "Rẻ, JSON schema strict ổn định",
            "en": "Cheap, strict schema"
          }
        },
        {
          "id": "luna",
          "label": {
            "vi": "gpt-6-luna (0.58$/tháng)",
            "en": "gpt-6-luna"
          },
          "note": {
            "vi": "Rẻ ngang Haiku",
            "en": "Same price"
          }
        },
        {
          "id": "glmf",
          "label": {
            "vi": "glm-5.3-flash (0.79$/tháng)",
            "en": "glm-5.3-flash"
          },
          "note": {
            "vi": "Luôn bật reasoning → token ra nhiều hơn dự tính",
            "en": "Always reasons"
          }
        },
        {
          "id": "kimi",
          "label": {
            "vi": "kimi-k3.1-pro (11.52$/tháng)",
            "en": "kimi-k3.1-pro"
          },
          "note": {
            "vi": "Đắt: ~12% vốn/tháng",
            "en": "~12% of capital/month"
          }
        }
      ]
    },
    {
      "id": "D6",
      "kind": "taste",
      "title": {
        "vi": "Trần đòn bẩy",
        "en": "Leverage cap"
      },
      "recommended": "x5",
      "question": {
        "vi": "Đòn bẩy tối đa (isolated)? Lỗ thật do SL quyết định, đòn bẩy chỉ quyết định tiền ký quỹ bị khoá.",
        "en": "Max leverage? Loss is set by SL; leverage only sets locked margin."
      },
      "options": [
        {
          "id": "x5",
          "label": {
            "vi": "5x",
            "en": "5x"
          },
          "note": {
            "vi": "Lệnh ~170 USDT chỉ khoá ~34 USDT; giá thanh lý cách ~19%, xa hơn SL rất nhiều",
            "en": "Liq ~19% away"
          }
        },
        {
          "id": "x3",
          "label": {
            "vi": "3x",
            "en": "3x"
          },
          "note": {
            "vi": "Khoá ~57 USDT/lệnh → 2 lệnh cùng lúc gần hết vốn",
            "en": "Locks more margin"
          }
        },
        {
          "id": "x10",
          "label": {
            "vi": "10x",
            "en": "10x"
          },
          "note": {
            "vi": "Thanh lý cách ~9%, nếu SL trượt khi biến động mạnh thì nguy hiểm",
            "en": "Liq ~9% away"
          }
        }
      ]
    },
    {
      "id": "D7",
      "kind": "taste",
      "depends_on": [
        "D4"
      ],
      "title": {
        "vi": "Ngưỡng được chạy tiền thật",
        "en": "Go-live gate"
      },
      "recommended": "strict",
      "question": {
        "vi": "Model phải đạt gì trên giấy mới được trade 100 USDT thật?",
        "en": "What must the model reach on paper?"
      },
      "options": [
        {
          "id": "strict",
          "label": {
            "vi": "≥ 40 lệnh giấy, PF ≥ 1.2 sau phí + tiền API, drawdown ≤ 20%, 0 lỗi thiếu SL, rồi ≥ 20 lệnh demo mới PF ≥ 1.0",
            "en": "≥40 trades, PF ≥1.2 net, DD ≤20%, 0 unprotected"
          },
          "note": {
            "vi": "Model không có lợi thế lọt ~15%. Không đạt → giấy thêm hoặc sửa prompt, không lên thật",
            "en": "Fail → extend paper"
          }
        },
        {
          "id": "time",
          "label": {
            "vi": "Chỉ cần chạy đủ 14 ngày không lỗi kỹ thuật",
            "en": "14 days without technical errors"
          },
          "note": {
            "vi": "Nhanh hơn, nhưng gần như chắc chắn đem model ngẫu nhiên ra tiền thật",
            "en": "May go live with a losing model"
          }
        }
      ]
    },
    {
      "id": "D8",
      "kind": "taste",
      "title": {
        "vi": "Báo Telegram",
        "en": "Telegram alerts"
      },
      "recommended": "yes",
      "question": {
        "vi": "Bot chạy tiền thật 24/7 có cần báo về điện thoại không?",
        "en": "Phone alerts for a 24/7 money bot?"
      },
      "options": [
        {
          "id": "yes",
          "label": {
            "vi": "Có: mỗi lệnh, lỗi, dừng ngày, tóm tắt 08:00",
            "en": "Yes"
          },
          "note": {
            "vi": "~40 dòng code; cần token bot",
            "en": "~40 lines; needs a bot token"
          }
        },
        {
          "id": "no",
          "label": {
            "vi": "Không, xem log/app Binance",
            "en": "No"
          },
          "note": {
            "vi": "Lỗi lúc 3h sáng không ai biết",
            "en": "Nobody sees a 3am error"
          }
        }
      ]
    }
  ]
}
```

## Round 1 — 2026-11-26T19:10:21Z
- C1: keep
- D1: h1
- D2: bes
- D3: r2
- D4: arena
- D6: x5
- D8: yes

## Round 2 — 2026-11-26T19:10:23Z
- D7: strict

## Decision — 2026-11-26T19:10:24Z
- action: approve
- C1: keep
- D1: h1
- D2: bes
- D3: r2
- D4: arena
- D6: x5
- D8: yes
- D7: strict

## Build notes — 2026-11-27
- Built on branch `1-llm-futures-bot`; independent review (ecc:python-reviewer) found no critical defect; 3 high + 9 lower items fixed in 0178ad9 and follow-up (flatten path, reconcile every 20 s, persisted hourly cycle, paper persistence + gap fills, MODE whitelist, limits ceilings, token/signature redaction, per-service keys).
- Deviation: open-interest change is not in the LLM snapshot (one more API call per symbol for little value); funding is.
- Deviation: protective orders use quantity + `reduceOnly`, not `closePosition=true` (ccxt path for closePosition unverified); the orphan sibling is cancelled by the 20 s reconcile. Revisit in AC5.
- Known limit: if a cycle raises, that hour is skipped (no retry, avoids LLM cost loops); SL/TP stay on the exchange and reconcile still runs every 20 s.
- Known limit: paper funding assumes 8 h for every symbol; SOL may be 4 h.
- Smoke on server-brandon-service (paper, invalid LLM key): data fetch from Binance FR OK, LLM 401 → hold, events written; image builds; `MODE=Live`/`prod` refused.
- Local `~/.config/anthropic/api-key.env` key returns 401 (invalid), so AC3 waits for the owner's keys.

## Owner changes — 2026-11-27 (chat)
1. No Binance demo key: the order-path checks (AC5–AC7) run on live with `trader.demo_check` at ~12 USDT SOL notional; the demo stage of the go-live gate is dropped.
2. Alerts go to Discord (`DISCORD_WEBHOOK_URL`), Telegram removed.
3. The bot (LLM + risk code) decides every trade by itself; no manual approval per trade (already the design).
4. News: recent headlines from Cointelegraph, Decrypt and The Block RSS go into the hourly snapshot (`trader/news.py`); the prompt treats them as data, not instructions. CoinDesk dropped (308 redirect from the server).
5. The live bot uses whichever LLM key is present, cheapest first (`trader/llm.py` PROVIDERS); compose service `live` (profile `live`).
- Live start still needs `LIVE_CONFIRM=I-ACCEPT-REAL-MONEY` and the owner's explicit choice on the report page.

## Report — 2026-11-27T05:43:32Z
- action: submit
- inputs provided: BINANCE_API_KEY, BINANCE_API_SECRET, LIVE_GO (values stored outside the docs)

## Live setup — 2026-11-27
- Owner chose "live now" on the report page (no demo, no paper). Server `.env` written (600): BINANCE_* + LIVE_CONFIRM; no LLM key given yet.
- OpenRouter added as provider (`OPENROUTER_API_KEY`, default model `anthropic/claude-haiku-5.5`, override `OPENROUTER_MODEL`).
- Futures wallet is empty (spot USDT ~0): AC5–AC7 live order check and the live start wait for 100 USDT in USDⓈ-M Futures and one LLM key.
