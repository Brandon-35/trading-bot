# LLM committee + multi-pair breakout strategy with aggressive-but-bounded sizing

Replace the single hourly LLM call on BTC/ETH/SOL with a deterministic signal engine across ~10 liquid alt perps; when a signal fires, a committee of cheap LLM analysts plus a bull/bear debate feeds one lead LLM that makes the final typed decision; code (not the LLM) owns sizing, stops and leverage. Goal set by the owner: grow the bot account from 18.74 USDT (+2 USD LLM credit) to 120–130 USDT, accepting high risk.

## Why
- **Who:** the owner, trading real money on Binance USDⓈ-M with a small test account (D10: 18 USDT month, FLOOR_EQUITY=12).
- **Current behavior:** one LLM (`upstage/solar-mini-4-5`) is asked every UTC hour about BTC/ETH/SOL (`bot/trader/main.py` cycle), risk 2%/trade, max 2 positions, 5x. BTC is nearly always skipped (min notional 50 USDT). One test trade so far, net −0.0327 USDT (fees).
- **Desired behavior:** trade many pairs continuously, only when a measurable setup exists; several LLMs argue and one lead decides; sizing aimed at fast growth without a high chance of ruin.
- **Why now:** owner request 2026-11-27 after reviewing the v2 dashboard.
- **Done when:** the Acceptance list below is ticked with evidence.

## Research findings (2026-11-27, three research agents)
- **No open-source or public multi-LLM debate bot has verified live profit.** TradingAgents (124k★) is backtest-only (3 months 2024, no debate ablation); Alpha Arena S1 (real money, single models): Qwen3 Max +22%, DeepSeek +4.9%, Claude −42%, Gemini −46%, Grok −58%, GPT-5 −59%; only 6 of 32 seasonal runs were profitable.
- **What separated winners from losers is trade frequency and fees, not intelligence:** Qwen ~43 trades won, Gemini ~238 trades lost (>13% of capital to fees). An arXiv study of 500–600 LLM agents (14,596 fills) found the fleet unprofitable; a mechanical bracket exit would have added +39 bps per position.
- **Usable edge evidence:** trend/breakout on 4h–6h bars across many coins (AdaptiveTrend, arXiv 2602.11708: OOS Sharpe 2.41 incl. costs, single-firm, unreplicated). Funding/OI/long-short ratios are useful as crowding filters, not entries.
- **Our own backtest (2026-11-27, public Binance 4h klines, 356 days, 10 alts, Donchian(20) breakout in the BTC trend + volume filter, 2-ATR stop, half at 2R, trailing 2.5 ATR, taker fees both sides):** 300 trades (0.84/day), win rate 29%, **average −0.037R per trade after fees** (first half −0.27R, second half +0.19R). The signal as specified has **no edge**; it is regime-dependent.
- **Monte Carlo with the real floor (bust = FLOOR_EQUITY 12, 2R wins / 1R losses, halving after 2 losses, 3,000 paths):**

| Start → target, floor | Edge after fees | Risk 3% | Risk 5% |
|---|---|---|---|
| 18.7 → 120, floor 12 | +0.10R | 65% reach / 27% halt, ~712 trades | 47% / 52%, ~377 trades |
| 18.7 → 120, floor 12 | +0.15R | 89% / 10%, ~533 trades | 68% / 32%, ~299 trades |
| 18.7 → 120, floor 5 | +0.10R | 79% / 2%, ~796 trades | 81% / 14%, ~491 trades |
| 100 → 230, floor 50 | +0.10R | 87% / 12%, ~294 trades | 70% / 30%, ~132 trades |
| 150 → 280, floor 75 | +0.15R | 96% / 4%, ~157 trades | 85% / 15%, ~76 trades |
| 18.7 → 120, floor 12, bootstrap of our backtest trades | ≈ −0.04R | 2–4% reach, 96% halt | |

  At ~1 trade/day, 300–700 trades is 1–2 years. The floor of 12 allows only a 36% drawdown while the target is 6.4x, so the small account is the binding constraint, not the strategy.
- **Hitting 6.7x inside one month** needs ~10–20x effective leverage: estimated 3–8% chance, 60–80% chance of hitting the floor (research agent estimate, not measured).
- **Fees at our size:** taker 0.05%/side; at 5% risk and a 2% stop, notional ≈ 2.5× equity, round trip ≈ 0.05R. Prefer limit (maker 0.02%) entries.
- **Binance minimum notional:** 516/522 USDT perps need only 5 USDT; ETH 20, BTC 50 → trade alts, use BTC/ETH as regime signals.
- **Lifetime account context:** the owner's hand trading since 2022 is −7,123 USDT net, including 27 liquidations (−1,893 USDT): liquidation avoidance must be enforced in code.

## Current state (verified 2026-11-27)
- `bot/trader/main.py`: `Bot.cycle` hourly; `act` validates via `risk.validate`; reconcile every 20 s; bot-owned scope by clientOrderId prefix (PR #6).
- `bot/trader/llm.py`: one OpenAI-compatible client, `pick()` chooses the first key present; OpenRouter only.
- `bot/trader/risk.py`: `Limits(leverage=5, risk_pct=0.02, max_positions=2, floor_equity)`; SL 0.5–3×ATR, R:R ≥ 1.5, daily stop 6%.
- `bot/trader/market.py`: snapshot with ATR/RSI/EMA 15m/1h/4h + funding for SYMBOLS.
- Tests: `cd bot && uv run pytest -q` → 39 passed.
- OpenRouter prices ($/1M in/out): deepseek-v3.2 0.26/0.38, qwen3-235b-a22b-2507 0.14/0.80, gemini-2.5-flash-lite 0.10/0.40, solar-mini-4-5 0.01/0.04, claude-sonnet-4.5 3/15.

## Scope
- In: universe scanner (top liquid alts, 5 USDT min notional), deterministic breakout signal + crowding filters, LLM committee (analysts → bull/bear → lead, typed JSON), new sizing rules, maker-first entries with taker fallback, trailing stop, trade-count cap, cost guard, paper shadow mode, dashboard "Hội đồng AI" view of each debate, docs/hub.
- Out: funding carry / delta-neutral (needs spot capital), scalping < 1h, on-chain data, new exchanges.
- Ordering: signal engine → committee → sizing/exits → paper shadow → live switch.
- Smallest version: 10 alts, one signal family (Donchian breakout + filters), 3 analysts + 1 debate round + 1 lead.
- Failure mode & rollback: bad code could open oversized or unprotected positions. Floor stop, reconcile (close unprotected bot positions every 20 s) and per-trade exchange SL stay. Rollback = redeploy previous commit (`docs/hub/infra.md`), `STRATEGY=v1` env flag keeps the old cycle available.

## Options
| Option | Change | Cost | Risk |
|---|---|---|---|
| A. Signal-gated committee (recommended) | code scans every 15 min; LLM committee runs only when a setup fires; lead decides; code sizes | ~3–6 committee runs/day ≈ $0.03–0.06/day | edge unproven; few trades at first |
| B. Committee every hour on every pair | committee analyses all pairs hourly | ≈ $0.2–0.3/day (> the 2 USD credit in ~8 days) | overtrading, fee drag (Alpha Arena losers' pattern) |
| C. Single model + cheap veto | no debate | cheapest | ignores owner's explicit debate requirement |

## Plan
### Phase 0 — read
- `bot/trader/{main,risk,market,llm,exchange,sync}.py`, tests. Pattern to copy: `risk.validate` returning a reject reason; `Store.log` events.
- Verify: notes of which functions change.
### Phase 1 — backtest harness + signal research (`bot/trader/backtest.py`)
- Walk-forward backtest on public 4h/1h klines (1–2 years, 10–20 alts) with taker/maker fees and funding; reports trades/day, win rate, avg R, max drawdown per half-year.
- Candidate signals: Donchian breakout (baseline, measured −0.037R), breakout + crowding filters (funding/OI history stored going forward), trend pullback (EMA20/50 on 4h in 1d trend), BTC-regime switch (trade only when BTC 1d trend strength > threshold).
- Edge gate: a signal goes to paper only with ≥ +0.10R avg after fees in BOTH halves out-of-sample and ≥ 150 trades. Until a live/paper edge ≥ +0.10R is measured over ≥ 30 trades, live risk is capped at 2% in code.
- Verify: `uv run python -m trader.backtest --signal <name>` prints the table; unit tests on synthetic candles.
### Phase 2 — universe + live signal engine (`bot/trader/signals.py`)
- Universe: top USDT perps by 24h volume with minNotional ≤ 5, excluding stock/commodity/ETF perps; BTC/ETH regime only. Scan every 15 min on closed bars. Start storing funding, OI, long/short and taker ratio per symbol every 15 min (Binance keeps ~30 days).
- Verify: dry scan against live public data logs setups.
### Phase 3 — committee (`bot/trader/committee.py`)
- Analysts (cheap model, parallel): technical, derivatives/flow, news/sentiment (RSS + Fear&Greed) → JSON {stance, confidence, key_points}.
- Bull and bear (cheap model) one round each, each answering the other's strongest point.
- Lead (D4 model) reads analysts + debate + last 10 closed bot trades → JSON {action: open|skip, side, confidence, sl_atr, tp_r, rationale}. Skip is default.
- Hourly open-position check: model may only tighten the stop or close, never widen.
- Every transcript stored as a `debate` event with its cost. Daily cost cap env `LLM_DAILY_USD` (default 0.10): exceeded → no new entries.
- Verify: tests with a fake LLM; one real committee run, transcript + cost stored.
### Phase 4 — sizing + exits (`risk.py`, `exchange.py`, `main.py`)
- Size from **bot value** (dashboard formula), not wallet equity (hand trades move the wallet).
- Risk per trade = D2 (capped at 2% until the edge gate passes), halved after 2 consecutive losses; total open risk across positions ≤ 10% (below the 12% daily stop); max 3 positions, max 2 on the same side; max 6 entries/day.
- Isolated margin; leverage chosen so the liquidation price is ≥ 2× the stop distance away (cap 10x); reject if size < min notional after halving.
- Entry: post-only limit 60 s, then market if the setup still holds. SL on exchange; TP1 half at 2R; trailing stop for the rest.
- **Reconcile fix:** a position is protected when a bot stop order covers the full remaining qty (TP no longer required after TP1); stop moves place the new stop before cancelling the old one.
- The `Paper` broker gets the same post-only/partial-TP/trailing path so paper exercises live logic.
- Verify: unit tests (sizing, total-risk cap, liq distance, min-notional reject, reconcile after TP1, stop replace order); real-exchange post-only place + cancel.
### Phase 5 — paper shadow (two arms)
- `paper_v2_signal` (signal only, no LLM) and `paper_v2_committee` (signal + committee) run side by side on live data, each its own DB, both on the dashboard.
- Window (D5): the chosen number of full paper trade lifecycles in the committee arm (and ≥ 20 committee runs), whichever comes later.
- Verify: zero errors in logs; both arms visible with trade lists.
### Phase 6 — dashboard + docs
- Tab "Hội đồng AI" (each debate: analysts, bull, bear, lead, cost) and a paper-vs-committee comparison; docs/hub features/decisions/changelog/env; hub-lint 0 errors.
### Live switch — separate step, NOT part of this plan's approval
- Needs the owner's explicit go after reading the paper results (repo rule: never change `live` without it).

## Risks & rollback
- No proven edge → losses: small trade count, measure after 30–50 trades; if EV after fees ≤ +0.1R, drop risk to 2% (rule written in code comments and decisions).
- LLM cost overrun → daily cap env, gate committee behind signals.
- Liquidation → liq distance ≥ 2× stop enforced before every order; isolated margin.
- Thin alt slippage → universe requires high 24h volume; spread check before entry.
- Hand trades on the same symbol → existing guard (no entry on a symbol with a hand position).
- Rollback → `STRATEGY=v1` or redeploy previous commit.

## Acceptance
<!-- Tick an item only with proof: replace the placeholder with `<command → decisive output line | screenshot path | URL>`; a tick without evidence counts as open. -->
- [x] AC0 — backtest harness reports fee-inclusive results for ≥ 3 signal candidates; edge gate documented — evidence: `python -m trader.backtest` 720 d, 4 signals × 4h/1h, fees incl.: 4h pullback +0.127R (1883 trades, halves +0.149/+0.109) passes EDGE_GATE on 30 alts; fails on 12 (+0.088); 1h no edge. ATR%-capped (tradable at 18.7 USDT) pullback: +0.119R overall but 2nd half +0.046R
- [x] AC1 — signal engine scans the alt universe every 15 min and logs setups; derivatives data stored (tests + live dry scan) — evidence: live: paper arms logged v2_scan + 2 pullback setups (BLESS, LISTA) at 15:31 ICT; deriv table 30 rows; signals.derivs(SOL) on server → funding 6.25e-05, ls 3.54, taker 0.52; tests test_signals.py
- [x] AC2 — committee: 3 analysts + bull/bear + lead produce a typed decision; transcript stored as `debate` event — evidence: real run on server `python -m trader.committee SOL/USDT:USDT` → 6 calls, lead JSON skip; live committee arm stored 2 `debate` events; test_committee.py 9 tests
- [x] AC3 — sizing from bot value, total-open-risk cap, liq distance, min-notional reject, 2% cap until edge gate, reconcile-after-TP1 and stop replacement enforced with tests — evidence: test_risk_v2.py + test_v2.py (45 tests) incl. reconcile-after-TP1, stop replace-before-cancel, min-notional reject, 2%→3% gate; live arm rejected BLESS/LISTA with `notional 1.75 < min notional 5.0` (not rounded up)
- [x] AC4 — LLM daily cost cap enforced; average committee cost per run measured — evidence: Budget cap LLM_DAILY_USD=0.10 tested (skip without any chat call); measured real cost $0.00059/run (SOL demo), $0.0007/run live (dashboard llm_today 0.0014 for 2 runs); PR #11 skips committee when unsizable
- [x] AC5 — maker-first entry with fallback and exchange SL/TP/trailing verified on the real exchange — evidence: DOGE live (6.5 USDT, 3x isolated): post-only GTX rested 20 s then market fallback {'qty':111,'maker':False}; STOP_MARKET 111 + TAKE_PROFIT_MARKET 55 on exchange; move_stop placed new stop 0.05742 then cancelled old; close → 0 positions, 0 triggers. Bug found+fixed: algo orders carry info.orderType (stop_cover was 0). Maker fill itself not observed
- [x] AC6 — both paper arms (signal-only, committee) deployed and running with no errors, visible on the dashboard; window counts per D5 tracked — evidence: server: trading-bot-paper-signal-1 / paper-committee-1 Up, 0 error/traceback lines in logs; /api/arms shows both arms, edge_gate 0/30; live container untouched (old image, Up)
- [x] AC7 — dashboard "Hội đồng AI" tab shows debates (browser QA desktop + mobile) — evidence: Docker Chromium on https://trade.brandondev.online #v2 and #committee at 1440 px and 390 px: KPI cards, comparison chart, debate cards with 3 analysts + bull/bear + lead; 0 overflow; mobile nav active tab visible after PR #14; anon/forged cookie → 401, bad arm → 400
- [x] AC8 — docs/hub updated, hub-lint 0 errors — evidence: docs/hub env/features/changelog/decisions(D12)/infra updated; `hub-lint .` → 0 error(s)
- [x] AC9 — all verify commands are green — evidence: `cd bot && uv run pytest -q` → 114 passed; `node --check bot/trader/static/app.js` ok

## Findings after deploy (2026-11-27)

- At 18.7 USDT and 2% risk the max stop for a 5 USDT min notional is ~7.5% of price. High-volatility alts (4h ATR ~10%) cannot be traded; the first two live setups were rejected for that. Their share of the backtest edge is large: ATR% ≤ 3.5% pullback keeps +0.119R overall but only +0.046R in the second half.
- Consequence: the paper arms will take fewer trades than the backtest and the tradable edge is weaker than the headline +0.127R. The 30-trade gate (D5) decides; no live switch before it.
- Fixed during QA: committee ran on unsizable setups (PR #11); derivatives/Fear&Greed not passed to the committee (PR #12); mobile nav hid the open tab (PR #13, #14); algo-order type detection (in PR #10).

## Files
| File | Change | churn/90d |
|---|---|---|
| `bot/trader/signals.py` | new: universe + breakout + crowding filters | 0 |
| `bot/trader/committee.py` | new: analysts, debate, lead, cost guard | 0 |
| `bot/trader/main.py` | 15-min scan loop, committee call, STRATEGY flag | 5 |
| `bot/trader/risk.py` | new sizing, liq distance, caps | 3 |
| `bot/trader/exchange.py` | post-only entry, trailing stop, partial TP | 4 |
| `bot/trader/llm.py` | multi-model calls with cost accounting | 2 |
| `bot/trader/dashboard.py`, `static/app.js` | debates API + tab | 3 |
| `bot/compose.yml`, `.env.example`, `docs/hub/*` | env + docs | 4 |
| `bot/tests/*` | new tests | 4 |

## Gate
```json
{
  "verdict": {
    "vi": "LỚN · tiền thật · 9 file",
    "en": "LARGE · real money · 9 files"
  },
  "triggers": [
    "H1",
    "H2"
  ],
  "tldr": {
    "vi": "Research + backtest: chưa có bằng chứng bot nhiều-AI-tranh-luận lãi thật; tín hiệu breakout 4h trên 10 altcoin trong 1 năm lỗ −0,037R/lệnh sau phí. Với 18,7 USDT và sàn 12, đạt 120 cần 300–700 lệnh (1–2 năm) ngay cả khi có lợi thế. Kế hoạch: làm bộ backtest để tìm tín hiệu có lợi thế thật → hội đồng AI (3 phân tích + bull/bear + lead) → quản lý vốn bằng code → paper 2 nhánh (chỉ tín hiệu vs có hội đồng). Chuyển tiền thật là bước riêng cần bạn đồng ý.",
    "en": "Research + backtest show no proven edge; a 1-year 4h breakout backtest is −0.037R/trade after fees. Build a backtest harness to find an edge, then the committee, code-owned sizing, two paper arms; live switch is a separate owner go."
  },
  "flow": {
    "before": [
      "Mỗi giờ 1 AI xem BTC/ETH/SOL",
      "Rủi ro 2%/lệnh, tối đa 2 vị thế"
    ],
    "after": [
      "Backtest tìm tín hiệu có lợi thế (≥ +0,1R sau phí)",
      "Mỗi 15 phút quét ~10 altcoin",
      "Có setup → 3 AI phân tích → bull vs bear → lead chốt",
      "Code tính khối lượng, đòn bẩy, SL/TP, trailing",
      "Paper 2 nhánh so sánh → bạn quyết định chuyển live"
    ]
  },
  "verify": [
    "cd bot && uv run pytest -q",
    "python3 ~/.claude/bin/hub-lint ."
  ],
  "files": [
    "bot/trader/*.py",
    "bot/trader/static/*",
    "bot/tests/*",
    "bot/compose.yml",
    "bot/.env.example",
    "docs/hub/*.md"
  ],
  "env_files": [
    "bot/.env.example"
  ],
  "target": "main",
  "task": "Brandon-35/trading-bot#9",
  "skills": [
    {
      "domain": "money/security",
      "skill": "ecc:llm-trading-agent-security",
      "phase": "build"
    },
    {
      "domain": "verify",
      "skill": "superpowers:verification-before-completion",
      "phase": "P6a"
    }
  ],
  "read": {
    "Why": {
      "h": "Vì sao",
      "md": "- **Ai:** bạn, tiền thật trên Binance Futures (tài khoản test 18,74 USDT).\n- **Đang là:** mỗi giờ 1 AI rẻ xem BTC/ETH/SOL, rủi ro 2%/lệnh. BTC gần như luôn bị bỏ vì lệnh tối thiểu 50 USDT.\n- **Nên là:** chạy liên tục nhiều cặp, chỉ vào lệnh khi có setup đo được; nhiều AI tranh luận, 1 AI lead chốt; quản lý vốn để tăng nhanh mà không dễ cháy.\n- **Xong khi:** các mục Nghiệm thu bên dưới có bằng chứng."
    },
    "Current state (verified 2026-11-27)": {
      "h": "Hiện trạng",
      "md": "- Bot: chu kỳ 1 giờ, 1 model `solar-mini`, rủi ro 2%, tối đa 2 vị thế, 5x, dừng ngày 6%, sàn 12 USDT.\n- Chỉ đụng lệnh của bot (PR #6). 39 test pass.\n- Giá model OpenRouter ($/1 triệu token vào/ra): deepseek-v3.2 0,26/0,38 · qwen3-235b 0,14/0,80 · gemini-flash-lite 0,10/0,40 · claude-sonnet-4.5 3/15."
    },
    "Options": {
      "h": "Các cách làm",
      "md": "| Cách | Sửa gì | Chi phí AI | Rủi ro |\n|---|---|---|---|\n| **A. Có tín hiệu mới gọi hội đồng (đề xuất)** | code quét 15 phút, chỉ khi có setup mới gọi 6 AI | ~$0,03–0,06/ngày | lợi thế chưa chứng minh; lúc đầu ít lệnh |\n| B. Hội đồng chạy mỗi giờ mọi cặp | AI phân tích hết | ~$0,2–0,3/ngày (hết 2 USD credit sau ~8 ngày) | đánh quá nhiều, phí ăn hết (kiểu thua ở Alpha Arena) |\n| C. 1 AI + 1 AI phủ quyết | không tranh luận | rẻ nhất | không đúng yêu cầu tranh luận của bạn |"
    },
    "Plan": {
      "h": "Các bước",
      "md": "1. **Backtest:** bộ backtest có phí + funding, thử ≥ 3 tín hiệu (breakout, breakout + lọc đám đông, pullback theo xu hướng, chỉ đánh khi BTC có xu hướng mạnh). Chỉ tín hiệu ≥ +0,1R sau phí ở cả 2 nửa dữ liệu mới được dùng. Chưa đo được lợi thế thật → code khoá rủi ro 2%/lệnh.\n2. **Quét:** ~10 altcoin thanh khoản cao mỗi 15 phút; bắt đầu lưu funding/OI/long-short.\n3. **Hội đồng AI:** 3 AI phân tích → Bull vs Bear 1 vòng → lead chốt JSON (mặc định không vào). Mỗi giờ AI chỉ được kéo SL chặt hơn/đóng. Lưu biên bản + chi phí; trần $0,10/ngày.\n4. **Vốn bằng code:** tính theo giá trị của bot (không theo ví có lệnh tay); rủi ro theo D2; tổng rủi ro đang mở ≤ 10%; tối đa 3 vị thế; thanh lý xa ≥ 2 lần SL; limit trước, market sau; chốt nửa ở 2R + trailing; sửa reconcile để không tự đóng sau khi chốt nửa.\n5. **Paper 2 nhánh:** chỉ-tín-hiệu vs có-hội-đồng, để biết AI tranh luận có giúp thật không.\n6. **Dashboard:** tab \"Hội đồng AI\" + so sánh 2 nhánh.\n7. **Chuyển tiền thật = bước riêng**, chỉ khi bạn đồng ý sau khi xem kết quả paper."
    },
    "Risks & rollback": {
      "h": "Rủi ro",
      "md": "- Không có lợi thế thật → lỗ: đo sau 30–50 lệnh; nếu lãi kỳ vọng sau phí ≤ +0,1R thì hạ rủi ro về 2%.\n- Tốn tiền AI → trần chi phí/ngày, chỉ gọi khi có tín hiệu.\n- Thanh lý → kiểm tra giá thanh lý trước mỗi lệnh, ký quỹ isolated.\n- Trượt giá altcoin mỏng → chỉ chọn cặp volume lớn, kiểm tra spread.\n- Quay lại bản cũ → `STRATEGY=v1` hoặc deploy commit trước."
    },
    "Acceptance": {
      "h": "Nghiệm thu",
      "md": "- AC0 backtest ≥ 3 tín hiệu có phí, ghi rõ ngưỡng lợi thế\n- AC1 quét 15 phút + lưu dữ liệu phái sinh\n- AC2 hội đồng 3+2+1 AI ra JSON, lưu biên bản\n- AC3 luật vốn (theo giá trị bot, trần tổng rủi ro, thanh lý, min notional, khoá 2%, reconcile sau TP1) có test\n- AC4 trần chi phí AI, đo chi phí/lần\n- AC5 lệnh limit + SL/TP/trailing kiểm trên sàn thật\n- AC6 2 nhánh paper chạy không lỗi, hiện trên dashboard\n- AC7 tab Hội đồng AI (desktop + mobile)\n- AC8 docs/hub, hub-lint 0 lỗi\n- AC9 test xanh"
    },
    "Files": {
      "h": "File",
      "md": "Mới: `signals.py`, `committee.py`. Sửa: `main.py`, `risk.py`, `exchange.py`, `llm.py`, `dashboard.py`, `static/app.js`, `compose.yml`, `.env.example`, `docs/hub/*`, tests."
    },
    "Research findings (2026-11-27, three research agents)": {
      "h": "Kết quả research + backtest",
      "md": "- **Chưa có bot nhiều-AI-tranh-luận nào chứng minh lãi thật.** TradingAgents chỉ backtest 3 tháng. Alpha Arena tiền thật: Qwen +22%, DeepSeek +4,9%, Claude −42%, Gemini −46%, Grok −58%, GPT-5 −59%; chỉ 6/32 lượt có lãi.\n- **Thắng/thua do số lệnh và phí:** Qwen ~43 lệnh thắng, Gemini ~238 lệnh thua (>13% vốn vào phí).\n- **Backtest của mình (1 năm, nến 4h, 10 altcoin, breakout theo xu hướng BTC, có phí):** 300 lệnh, thắng 29%, **trung bình −0,037R/lệnh** (nửa đầu −0,27R, nửa sau +0,19R) → tín hiệu này chưa có lợi thế.\n- **Monte Carlo với sàn 12 thật:**\n\n| Vốn → mục tiêu, sàn | Lợi thế | Rủi ro 3% | Rủi ro 5% |\n|---|---|---|---|\n| 18,7 → 120, sàn 12 | +0,10R | 65% đạt / 27% dừng, ~712 lệnh | 47% / 52%, ~377 lệnh |\n| 18,7 → 120, sàn 12 | +0,15R | 89% / 10%, ~533 lệnh | 68% / 32%, ~299 lệnh |\n| 18,7 → 120, sàn 5 | +0,10R | 79% / 2%, ~796 lệnh | 81% / 14%, ~491 lệnh |\n| 100 → 230, sàn 50 | +0,10R | 87% / 12%, ~294 lệnh | 70% / 30%, ~132 lệnh |\n| 150 → 280, sàn 75 | +0,15R | 96% / 4%, ~157 lệnh | 85% / 15%, ~76 lệnh |\n| 18,7 → 120 với tín hiệu đã backtest | ≈ −0,04R | 2–4% đạt, 96% dừng | |\n\n- ~1 lệnh/ngày → 300–700 lệnh là 1–2 năm. **Vốn nhỏ + sàn 12 (chỉ cho sụt 36%) mới là nút thắt**, không phải chiến lược.\n- Lịch sử tài khoản: −7.123 USDT, 27 lần thanh lý → chống thanh lý phải nằm trong code."
    }
  },
  "decisions": [
    {
      "id": "D1",
      "kind": "challenge",
      "title": {
        "vi": "Vốn và mục tiêu 120–130 USDT",
        "en": "Capital and the 120–130 USDT target"
      },
      "you_said": "Bot chạy liên tục, mục tiêu trước mắt ~120–130 USDT (bù cả tiền AI), chấp nhận rủi ro cao, vốn hiện 18,7 USDT.",
      "we_recommend": "Nạp thêm vốn lên 100–150 USDT, mục tiêu lời +100–130 USDT, sàn = 50% vốn. Hoặc giữ 18,7 nhưng hạ sàn xuống 5 (coi 18,7 là tiền chấp nhận mất).",
      "why": "Monte Carlo với sàn 12: dù có lợi thế +0,1R, rủi ro 5% → 52% bị dừng và cần ~377 lệnh (~1 năm). Với 100 → 230, sàn 50, rủi ro 3%: 87% đạt, 12% dừng, ~294 lệnh; vốn 150 rủi ro 5%: ~76–92 lệnh (~3 tháng).",
      "missing": "Không biết bạn có muốn nạp thêm không; tiền nạp thêm cũng là tiền có thể mất.",
      "cost_if_wrong": "Giữ 18,7 + sàn 12: khả năng cao bot chạm sàn và tự dừng trước khi tới 120.",
      "recommended": "keep",
      "options": [
        {
          "id": "keep",
          "label": {
            "vi": "Giữ 18,7 USDT, sàn 12, mục tiêu 120 (ý bạn)",
            "en": "Keep 18.7, floor 12, target 120 (owner's)"
          }
        },
        {
          "id": "fund",
          "label": {
            "vi": "Nạp lên 100–150 USDT, mục tiêu +100–130, sàn 50% (đề xuất)",
            "en": "Fund 100–150, target +100–130, floor 50% (recommended)"
          }
        },
        {
          "id": "lottery",
          "label": {
            "vi": "Giữ 18,7 nhưng hạ sàn xuống 5 (chấp nhận mất hết)",
            "en": "Keep 18.7, floor 5 (accept total loss)"
          }
        }
      ]
    },
    {
      "id": "D2",
      "kind": "taste",
      "depends_on": [
        "D1"
      ],
      "title": {
        "vi": "Rủi ro mỗi lệnh khi đã chứng minh có lợi thế",
        "en": "Risk per trade once an edge is proven"
      },
      "question": {
        "vi": "Trước khi đo được lợi thế (≥ 30 lệnh, ≥ +0,1R), code luôn khoá 2%. Sau đó dùng mức nào?",
        "en": "Code caps at 2% until an edge is measured. Which level after that?"
      },
      "recommended": "r3",
      "options": [
        {
          "id": "r3",
          "label": {
            "vi": "3% (đề xuất)",
            "en": "3% (recommended)"
          },
          "note": {
            "vi": "tỉ lệ dừng thấp nhất trong bảng",
            "en": "lowest halt rate"
          }
        },
        {
          "id": "r5",
          "label": {
            "vi": "5%",
            "en": "5%"
          },
          "note": {
            "vi": "nhanh gấp ~2 lần, tỉ lệ dừng gấp ~2–3 lần",
            "en": "~2x faster, ~2–3x halt rate"
          }
        }
      ]
    },
    {
      "id": "D3",
      "kind": "taste",
      "title": {
        "vi": "Khi nào gọi hội đồng AI",
        "en": "When the AI committee runs"
      },
      "question": {
        "vi": "Hội đồng 6 AI chạy khi nào?",
        "en": "When does the 6-model committee run?"
      },
      "recommended": "gated",
      "options": [
        {
          "id": "gated",
          "label": {
            "vi": "Chỉ khi code thấy setup (đề xuất)",
            "en": "Only on a code setup (recommended)"
          },
          "note": {
            "vi": "~$0,03–0,06/ngày, tránh đánh quá nhiều",
            "en": "cheap"
          }
        },
        {
          "id": "hourly",
          "label": {
            "vi": "Mỗi giờ, mọi cặp",
            "en": "Hourly, all pairs"
          },
          "note": {
            "vi": "~$0,2–0,3/ngày, hết credit 2 USD sau ~8 ngày",
            "en": "burns credit in ~8 days"
          }
        }
      ]
    },
    {
      "id": "D4",
      "kind": "taste",
      "title": {
        "vi": "AI lead (chốt lệnh)",
        "en": "Lead model"
      },
      "question": {
        "vi": "Model nào làm lead? AI phân tích và bull/bear dùng model rẻ (qwen3-235b / gemini-flash-lite).",
        "en": "Lead model; analysts use cheap models."
      },
      "recommended": "deepseek",
      "options": [
        {
          "id": "deepseek",
          "label": {
            "vi": "DeepSeek V3.2 (đề xuất)",
            "en": "DeepSeek V3.2 (recommended)"
          },
          "note": {
            "vi": "~$0,003/lần",
            "en": "~$0.003/run"
          }
        },
        {
          "id": "qwen",
          "label": {
            "vi": "Qwen3 235B",
            "en": "Qwen3 235B"
          },
          "note": {
            "vi": "rẻ, dòng Qwen thắng Alpha Arena mùa 1",
            "en": "Qwen won S1"
          }
        },
        {
          "id": "sonnet",
          "label": {
            "vi": "Claude Sonnet 4.5",
            "en": "Claude Sonnet 4.5"
          },
          "note": {
            "vi": "~$0,05/lần, đắt ~15 lần",
            "en": "~15x cost"
          }
        }
      ]
    },
    {
      "id": "D5",
      "kind": "taste",
      "title": {
        "vi": "Paper chạy bao nhiêu lệnh trước khi bạn xem xét chuyển live",
        "en": "Paper window before the live decision"
      },
      "question": {
        "vi": "Nhánh có hội đồng cần bao nhiêu lệnh paper hoàn chỉnh trước khi đưa kết quả cho bạn quyết định chuyển tiền thật?",
        "en": "How many complete paper trades before the live decision?"
      },
      "recommended": "n30",
      "options": [
        {
          "id": "n10",
          "label": {
            "vi": "10 lệnh (~1–2 tuần)",
            "en": "10 trades"
          },
          "note": {
            "vi": "chỉ bắt lỗi code, chưa nói gì về lời/lỗ",
            "en": "catches bugs only"
          }
        },
        {
          "id": "n30",
          "label": {
            "vi": "30 lệnh (~1 tháng) (đề xuất)",
            "en": "30 trades (recommended)"
          },
          "note": {
            "vi": "bắt đầu đo được lợi thế",
            "en": "starts to measure edge"
          }
        }
      ]
    }
  ]
}
```

## Round 1 — 2026-11-27T08:14:42Z
- D1: keep
- D3: gated
- D4: deepseek
- D5: n30

## Round 2 — 2026-11-27T08:14:42Z
- D2: r3

## Decision — 2026-11-27T08:14:44Z
- action: approve
- D1: keep
- D3: gated
- D4: deepseek
- D5: n30
- D2: r3
