"""Main loop: every minute fill paper stops; on every 1h close ask the LLM and act within the risk rules.

MODE=paper (default) | demo | live. Live also needs LIVE_CONFIRM=I-ACCEPT-REAL-MONEY.
`python -m trader.main --clear-halt` lifts a full stop after the owner has looked at it.
`python -m trader.main --once` runs one decision cycle and exits (smoke test).
"""
import logging
import math
import os
import sys
import time

import httpx

from . import notify, sync
from .exchange import Binance, Paper, make_ccxt
from .llm import LLM
from .market import snapshot
from .news import headlines
from .risk import (Limits, V2Limits, check_caps, halt_reason, open_risk, pick_leverage, risk_pct, size, size_v2,
                   validate)
from .store import Store

log = logging.getLogger("bot")
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT").split(",")


def halted(store: Store) -> bool:
    q = "SELECT COALESCE(MAX(rowid), 0) FROM events WHERE kind = ?"
    return store.db.execute(q, ("halt",)).fetchone()[0] > store.db.execute(q, ("halt_clear",)).fetchone()[0]


class Bot:
    def __init__(self, broker, llm, store: Store, limits: Limits, mode: str):
        self.broker, self.llm, self.store, self.limits, self.mode = broker, llm, store, limits, mode
        self.foreign: set[str] = set()   # symbols holding a position the bot does not own (hand trades)
        self._warned: dict[str, float] = {}
        if mode != "paper":
            sync.init(store.db)

    def owned(self, symbol: str, p: dict) -> bool:
        """A position is the bot's only if the bot's own fills add up to exactly its size; unknown = not ours."""
        if self.mode == "paper":
            return True
        q = sync.bot_open_qty(self.store.db, sync.bot_start_ms()).get(symbol, 0.0)
        return abs(q - (p["qty"] if p["side"] == "long" else -p["qty"])) < 1e-9

    def mine(self, positions: dict) -> dict:
        """Bot-owned positions on bot symbols; everything else is left strictly alone."""
        out, self.foreign = {}, set()
        for s, p in positions.items():
            if s not in SYMBOLS:
                continue
            if self.owned(s, p):
                out[s] = p
            else:
                self.foreign.add(s)
                if time.time() - self._warned.get(s, 0) > 3600:
                    self._warned[s] = time.time()
                    log.info("%s: position is not the bot's, ignored", s)
        return out

    def day_start_equity(self, equity: float) -> float:
        """Equity at the start of the UTC day: the last equity seen before midnight, so downtime over
        midnight cannot erase a loss. Call before logging the current equity."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        d = self.store.last("day_start")
        if d and d["date"] == today:
            return d["equity"]
        prev = self.store.last("equity")
        start = prev["equity"] if prev else equity
        self.store.log("day_start", date=today, equity=start)
        return start

    def reconcile(self, positions: dict):
        """The exchange is the source of truth: no position without both protective orders, no orphans."""
        if self.mode == "paper":
            return
        mine = self.mine(positions)
        for s in SYMBOLS:
            n = self.broker.protective_count(s)
            if s in mine and n < 2:
                self.broker.close(s)
                self.store.log("reconcile_close", symbol=s, protective=n)
                notify.send(f"⚠️ {notify.coin(s)}: thiếu lệnh bảo vệ ({n}/2), đã đóng vị thế")
            elif s not in positions and n:   # bot trigger orders only (protective_count)
                self.broker.cancel_protective(s)
                self.store.log("reconcile_cancel", symbol=s, orders=n)

    def cycle(self):
        if halted(self.store):
            log.info("halted, waiting for --clear-halt")
            return
        self.reconcile(self.broker.positions())
        positions = self.mine(self.broker.positions())
        equity = self.broker.equity()
        day_start = self.day_start_equity(equity)
        self.store.log("equity", equity=equity, positions=positions)
        stop = halt_reason(equity, day_start, self.limits)
        if stop == "floor":
            for s in list(positions):
                self.broker.close(s)
            self.store.log("halt", equity=equity)
            notify.send(f"🛑 DỪNG HẲN: vốn {notify.num(equity)} < {notify.num(self.limits.floor_equity)} USDT, đã đóng hết. "
                        "Mở lại: `python -m trader.main --clear-halt`")
            return

        snap, ref = snapshot(self.broker.data, SYMBOLS)
        decisions, meta = self.llm.decide({"time_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
                                           "equity": round(equity, 2), "open_positions": positions, "symbols": snap,
                                           "news": headlines()})
        self.store.log("llm_call", **meta)
        if "error" in meta:
            notify.send(f"⚠️ AI lỗi, giữ nguyên vị thế: {meta['error'][:200]}")

        for d in decisions:
            reason = self.act(d, positions, ref, equity, stop)
            self.store.log("decision", **d.model_dump(), accepted=reason is None, reject=reason)
            positions = self.mine(self.broker.positions())

    def act(self, d, positions, ref, equity, stop) -> str | None:
        if d.symbol not in SYMBOLS:
            return "symbol not allowed"
        if d.action == "hold":
            return None
        if d.action == "close":
            if d.symbol not in positions:
                return "no position to close"
            self.broker.close(d.symbol)
            notify.card(f"🤖 AI ĐÓNG · {notify.coin(d.symbol)}", color=notify.YELLOW, reason=d.reason)
            return None
        if stop == "daily":
            return "daily loss stop active"
        if d.symbol in positions:
            return "position already open"
        if d.symbol in self.foreign:
            return "manual position on this symbol"
        if len(positions) >= self.limits.max_positions:
            return "max positions reached"
        price, atr = ref[d.symbol]["price"], ref[d.symbol]["atr"]
        why = validate(d.action, price, d.stop_loss, d.take_profit, d.confidence, atr, self.limits)
        if why:
            return why
        m = self.broker.market(d.symbol)
        qty, why = size(equity, self.broker.free_margin(), price, d.stop_loss, m["precision"]["amount"],
                        m["limits"]["amount"]["min"] or 0, m["limits"]["cost"]["min"] or 5, self.limits)
        if why:
            return why
        try:
            self.broker.open(d.symbol, d.action, qty, d.stop_loss, d.take_profit)
        except Exception as e:
            notify.send(f"⚠️ {notify.coin(d.symbol)}: vào lệnh lỗi, đã đóng: {type(e).__name__}: {e}"[:300])
            return f"order failed: {type(e).__name__}"
        self.store.log("trade_open", symbol=d.symbol, side=d.action, qty=qty, price=price,
                       sl=d.stop_loss, tp=d.take_profit, confidence=d.confidence)
        notify.opened(d.symbol, d.action, qty, price, d.stop_loss, d.take_profit, self.limits.leverage,
                      qty * abs(price - d.stop_loss), qty * abs(price - d.stop_loss) / equity if equity else 0, d.reason)
        return None

    def daily_summary(self):
        e = self.store.last("equity") or {}
        cost = self.store.db.execute(
            "SELECT COALESCE(SUM(json_extract(data,'$.cost')),0) FROM events WHERE kind='llm_call'").fetchone()[0]
        open_ = [notify.coin(x) for x in (e.get('positions') or {})]
        notify.card("📊 Tóm tắt ngày", [f"**Vốn:** {notify.num(e.get('equity', 0))} USDT",
                                       f"**Đang mở:** {', '.join(open_) or 'không có'}",
                                       f"**Chi phí AI từ đầu:** ${cost:.3f}"], notify.BLUE)


class BotV2(Bot):
    """Signal scan (+ optional LLM committee) with code-owned sizing, maker-first entries, partial TP and a trailing stop.

    `signals` / `committee` are the modules (injected so tests can fake them). Per-position state (stop, ATR, TP1 done,
    high-water mark) lives in `self.state`, persisted as a v2_state event so a restart keeps trailing.
    """
    TRAIL_ATR, MIN_STEP_ATR = 2.5, 0.1

    def __init__(self, broker, store: Store, limits: V2Limits, mode: str, arm: str, signals, committee=None,
                 budget=None, signal: str | None = None, universe_n: int = 10):
        super().__init__(broker, None, store, limits, mode)
        self.arm, self.signals, self.committee, self.budget = arm, signals, committee, budget
        self.signal, self.universe_n, self._uni = signal, universe_n, None
        self.state: dict = (store.last("v2_state") or {}).get("pos", {})

    def _save_state(self):
        self.store.log("v2_state", pos=self.state)

    def mine(self, positions: dict) -> dict:
        """Bot-owned positions on ANY symbol (the universe moves); hand positions are left strictly alone."""
        out, self.foreign = {}, set()
        for s, p in positions.items():
            if self.owned(s, p):
                out[s] = p
            else:
                self.foreign.add(s)
        return out

    def base(self) -> float:
        """The bot's own money, never the wallet (hand trades move the wallet)."""
        if self.mode == "paper":
            return self.broker.equity()
        return sync.values(self.store.db)["futures_value"]

    def reconcile(self, positions: dict):
        """A bot position needs a bot stop covering its full remaining qty (a TP is optional: v2 after TP1 has
        none). Unprotected -> closed at market. Orders left behind by a vanished position -> cancelled."""
        for s, p in self.mine(positions).items():
            cover = self.broker.stop_cover(s)
            if cover < p["qty"] * (1 - 1e-6):
                self.broker.close(s)
                self.store.log("reconcile_close", symbol=s, cover=cover, qty=p["qty"])
                notify.send(f"⚠️ {notify.coin(s)}: stop chỉ phủ {cover}/{p['qty']}, đã đóng vị thế")
        for s in list(self.state):
            if s not in positions:
                n = self.broker.protective_count(s)
                if n:
                    self.broker.cancel_protective(s)
                    self.store.log("reconcile_cancel", symbol=s, orders=n)
                del self.state[s]
                self._save_state()

    # ---- stops ------------------------------------------------------------------------------------------------
    def _set_stop(self, s, st, target, qty, price, why) -> bool:
        """Move the stop to `target` (new order first, old cancelled after). A target already breached by the
        price means the stop would fire at once, so the position is closed instead."""
        sg = 1 if st["side"] == "long" else -1
        if (price - target) * sg <= 0:
            self.broker.close(s)
            self.store.log("stop_breach_close", symbol=s, target=target, price=price, why=why)
            notify.card(f"⚠️ ĐÓNG · {notify.coin(s)}", [f"Giá {notify.price(price)} đã vượt stop mới {notify.price(target)} ({notify.WHY.get(why, why)})"], notify.YELLOW)
            return False
        try:
            self.broker.move_stop(s, target, qty)
        except Exception as e:
            log.warning("move_stop %s: %s", s, notify.redact(f"{type(e).__name__}: {e}")[:200])
            return False
        st["stop"] = target
        self.store.log("stop_move", symbol=s, stop=target, why=why)
        self._save_state()
        return True

    def trail(self):
        """Every pass: detect TP1 (qty shrank) -> stop to breakeven on the remaining qty; then trail at 2.5 ATR,
        only ever in the favourable direction."""
        positions = self.broker.positions()
        for s, st in list(self.state.items()):
            p = positions.get(s)
            if not p:
                continue
            try:
                price = float(self.broker.data.fetch_ticker(s)["last"])
            except Exception:
                continue
            sg = 1 if st["side"] == "long" else -1
            st["extreme"] = max(st["extreme"], price) if sg > 0 else min(st["extreme"], price)
            first = False
            if not st["tp1_done"] and st["tp_qty"] > 0 and p["qty"] <= st["qty0"] - 0.9 * st["tp_qty"]:
                st["tp1_done"] = first = True
                self.store.log("tp1", symbol=s, qty=p["qty"])
            if not st["tp1_done"]:
                continue
            cand = st["extreme"] - sg * self.TRAIL_ATR * st["atr"]
            target = max(st["stop"], st["entry"], cand) if sg > 0 else min(st["stop"], st["entry"], cand)
            if first or (target - st["stop"]) * sg >= self.MIN_STEP_ATR * st["atr"]:
                self._set_stop(s, st, target, p["qty"], price, "breakeven" if first else "trail")

    def manage_hourly(self):
        """Committee arm only: the model may tighten a stop or close, never widen."""
        if self.arm != "committee":
            return
        positions = self.broker.positions()
        for s, st in list(self.state.items()):
            p = positions.get(s)
            if not p or (self.budget and not self.budget.ok()):
                continue
            price = float(self.broker.data.fetch_ticker(s)["last"])
            sg = 1 if st["side"] == "long" else -1
            pos = {"symbol": s, "side": st["side"], "qty": p["qty"], "entry": st["entry"], "stop": st["stop"],
                   "tp": st["tp"], "atr": st["atr"], "mark": price, "tp1_done": st["tp1_done"],
                   "r_now": (price - st["entry"]) * sg / st["dist0"], "hours_open": (time.time() * 1000 - st["opened"]) / 3.6e6}
            res = self.committee.manage(pos, self._ctx(s), self.store)
            self.store.log("manage", symbol=s, **{k: res.get(k) for k in ("action", "new_stop", "rationale")})
            if res.get("action") == "close":
                self.broker.close(s)
                notify.card(f"🤖 AI ĐÓNG SỚM · {notify.coin(s)}", color=notify.YELLOW, reason=res.get("rationale", ""))
            elif res.get("action") == "tighten":
                try:
                    ns = float(res["new_stop"])
                except (KeyError, TypeError, ValueError):
                    continue
                if (ns - st["stop"]) * sg > 0:           # strictly tighter than the current stop
                    self._set_stop(s, st, ns, p["qty"], price, "committee")

    # ---- entries ----------------------------------------------------------------------------------------------
    def universe(self) -> list[str]:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if not self._uni or self._uni[0] != day:
            self._uni = (day, self.signals.universe(self.broker.data, self.universe_n))
        return self._uni[1]

    def closed_r(self) -> list[float]:
        return [e["r"] for e in self.store.all("trade_close") if e.get("r") is not None]

    def entries_today(self) -> int:
        t = time.gmtime()
        midnight = int(time.time()) - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec)
        return self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='trade_open' AND ts >= ?",
                                     (midnight,)).fetchone()[0]

    def _ctx(self, s: str, setup: dict | None = None) -> dict:
        """Market context for the committee: derivatives for the symbol, Fear & Greed, BTC trend."""
        f = (setup or {}).get("features") or {}
        return {"time_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
                "derivs": self.signals.derivs(self.store.db, s), "fear_greed": self._fear_greed(),
                "btc": {k: f[k] for k in ("btc_trend", "btc_strength") if k in f}}

    @staticmethod
    def _fear_greed():
        try:
            return int(httpx.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()["data"][0]["value"])
        except Exception:
            return None

    @staticmethod
    def _news() -> list:
        try:
            return headlines()
        except Exception:
            return []

    def scan_cycle(self):
        if halted(self.store):
            return
        all_pos = self.broker.positions()
        mine = self.mine(all_pos)
        base = self.base()
        day_start = self.day_start_equity(base)
        self.store.log("equity", equity=base, positions=mine)
        stop = halt_reason(base, day_start, self.limits)
        if stop == "floor":
            for s in list(mine):
                self.broker.close(s)
            self.store.log("halt", equity=base)
            notify.send(f"🛑 FULL STOP: base {base:.2f} < {self.limits.floor_equity}. Positions closed. "
                        "Run `python -m trader.main --clear-halt` to resume.")
            return
        if stop == "daily":
            return
        syms = self.universe()
        self.signals.store_derivs(self.broker.data, self.store.db, syms)
        sig = self.signal or self.signals.best_signal() or "breakout"
        for setup in self.signals.scan(self.broker.data, syms, sig, "4h"):
            self.enter(setup, base)

    def enter(self, setup: dict, base: float):
        s, side, price, atr, bar = setup["symbol"], setup["side"], setup["price"], setup["atr"], setup["bar_time"]
        seen = self.store.db.execute(
            "SELECT 1 FROM events WHERE kind='setup' AND json_extract(data,'$.symbol')=? AND json_extract(data,'$.bar_time')=?",
            (s, bar)).fetchone()
        if seen:
            return                                  # the same closed bar is rescanned every 15 min: act once
        self.store.log("setup", symbol=s, bar_time=bar, side=side, signal=setup.get("signal"), price=price, atr=atr)
        conf, why = None, ""
        reject = lambda r: self._decision(s, side, None, None, conf, why, r)
        if s in self.broker.positions():
            return reject("position already open (bot or hand)")
        if self.signals.crowded(self.store.db, s, side):
            return reject("crowded")
        mine = self.mine(self.broker.positions())
        listed = [{"side": self.state[x]["side"], "risk": open_risk(
            self.state[x]["side"], mine[x]["qty"], self.state[x]["entry"], self.state[x]["stop"])}
            for x in mine if x in self.state]
        if len(listed) != len(mine):                 # a position without state: risk unknown, take no more
            return reject("bot position without state")
        lim, today = self.limits, self.entries_today()
        if (r := check_caps(listed, side, 0.0, today, base, lim)):
            return reject(r)
        mult, tp_r = (setup.get("stop_dist") or 2.0 * atr) / atr, 2.0     # the signal's own stop (2 ATR today), TP1 at 2R
        why = "signal"
        if self.arm == "committee":
            m = self.broker.market(s)   # no LLM spend on a setup even the lead's tightest stop (1 ATR) cannot size
            _, r = size_v2(base, risk_pct(self.closed_r(), lim), max(atr, lim.sl_min_pct * price), price,
                           m["precision"]["amount"], m["limits"]["amount"]["min"] or 0, m["limits"]["cost"]["min"] or 0,
                           lim)
            if r:
                return reject(f"unsizable before committee: {r}")
            if self.budget and not self.budget.ok():
                return reject("LLM daily budget used")
            recent = [{k: e.get(k) for k in ("symbol", "side", "r", "why")} for e in self.store.all("trade_close")[-10:]]
            ctx = self._ctx(s, setup) | {"base": round(base, 2),
                   "news": self._news(),
                   "open_positions": {x: {"side": self.state[x]["side"], "entry": self.state[x]["entry"],
                                          "stop": self.state[x]["stop"]} for x in mine}}
            res = self.committee.decide(setup, ctx, recent, self.store)
            conf, why = res.get("confidence"), str(res.get("rationale") or "")
            if res.get("action") != "open":
                return reject("committee skip")
            if res.get("side") != side:
                return reject(f"committee side {res.get('side')} != setup {side}")
            mult, tp_r = res.get("sl_atr"), res.get("tp_r")
            if not (isinstance(mult, (int, float)) and isinstance(tp_r, (int, float)) and 1.0 <= mult <= 3.0
                    and 1.0 <= tp_r <= 4.0):
                return reject(f"committee sl_atr/tp_r out of range: {mult}/{tp_r}")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (price, atr)):
            return reject("non-finite market data")
        dist = mult * atr
        if dist < lim.sl_min_pct * price:
            return reject(f"stop too tight: {dist:.6g} < {lim.sl_min_pct:.1%} of price")
        sg = 1 if side == "long" else -1
        sl, tp = price - sg * dist, price + sg * tp_r * dist
        rp = risk_pct(self.closed_r(), lim)
        m = self.broker.market(s)
        qty, r = size_v2(base, rp, dist, price, m["precision"]["amount"], m["limits"]["amount"]["min"] or 0,
                         m["limits"]["cost"]["min"] or 0, lim)
        if r:
            return reject(r)
        if (r := check_caps(listed, side, qty * dist, today, base, lim)):
            return reject(r)
        used = sum(self.state[x]["entry"] * mine[x]["qty"] / self.state[x]["lev"] for x in mine)
        lev, r = pick_leverage(qty * price, min(self.broker.free_margin(), base - used), price, dist, lim)
        if r:
            return reject(r)
        try:
            fill = self.broker.open_v2(s, side, qty, sl, tp, price, atr, lev)
        except Exception as e:
            notify.send(f"⚠️ {s} entry failed, flattened: {type(e).__name__}: {e}"[:300])
            return reject(f"order failed: {type(e).__name__}")
        if not fill:
            return reject("entry not filled (price moved away)")
        self.state[s] = {"side": side, "qty0": fill["qty"], "entry": fill["entry"], "stop": sl, "stop0": sl, "tp": tp,
                         "tp_qty": fill["tp_qty"], "atr": atr, "dist0": dist, "tp1_done": False,
                         "extreme": fill["entry"], "opened": int(time.time() * 1000), "lev": lev}
        self._save_state()
        self.store.log("trade_open", symbol=s, side=side, qty=fill["qty"], price=fill["entry"], sl=sl, tp=tp,
                       tp_r=tp_r, risk_pct=rp, leverage=lev, arm=self.arm, maker=fill["maker"],
                       risk=fill["qty"] * dist, confidence=conf)
        self._decision(s, side, sl, tp, conf, why, None)
        notify.opened(s, side, fill["qty"], fill["entry"], sl, tp, lev, fill["qty"] * dist, rp,
                      "" if why == "signal" else why, tp_label="Chốt ½ ở")

    def _decision(self, s, side, sl, tp, conf, why, reject):
        self.store.log("decision", symbol=s, action=side if reject is None else "hold", stop_loss=sl, take_profit=tp,
                       confidence=conf, reason=why or reject, accepted=reject is None, reject=reject)


def run_v2(mode: str, store: Store):
    """v2 loop. Paper only for now (guarded in main): the owner must give a separate go before it trades real money."""
    from . import signals
    arm = os.getenv("ARM", "signal")
    if arm not in ("signal", "committee"):
        sys.exit(f"ARM must be signal or committee, got {arm!r}")
    committee = budget = None
    if arm == "committee":
        from . import committee
        budget = committee.Budget(store)
    limits = V2Limits(risk_pct=float(os.getenv("RISK_PCT", "0.02")),
                      risk_pct_proven=float(os.getenv("RISK_PCT_PROVEN", "0.03")),
                      floor_equity=float(os.getenv("FLOOR_EQUITY", "12")))
    ex = make_ccxt(mode)
    on_close = lambda **t: (store.log("trade_close", **t),
                            notify.closed(t["symbol"], t["pnl"], t["why"], t["r"]))
    broker = Paper(ex, 1, float(os.getenv("PAPER_START", "18.7392")), on_close,
                   state=store.last("paper_state"), save=lambda st: store.log("paper_state", **st), funding=False)
    bot = BotV2(broker, store, limits, mode, arm, signals, committee, budget, os.getenv("SIGNAL") or None,
                int(os.getenv("UNIVERSE_N", "10")))
    notify.started([f"**Chế độ:** {'tiền ảo' if mode == 'paper' else mode}",
                     *( [f"**Model AI:** {committee.LEAD_MODEL}"] if committee else [] ),
                     f"**Dừng hẳn khi vốn <** {notify.num(limits.floor_equity)} USDT"])
    last_day = None
    while True:
        try:
            broker.tick()
            bot.reconcile(broker.positions())
            bot.trail()
            now = time.time()
            for kind, key, ready, fn in (("v2_scan", int(now // 900), now % 900 >= 5, bot.scan_cycle),
                                         ("v2_manage", time.strftime("%Y-%m-%dT%H", time.gmtime(now)),
                                          now % 3600 >= 5, bot.manage_hourly)):
                done = store.last(kind)
                if ready and (not done or done["key"] != key):
                    store.log(kind, key=key)         # persisted first: a crash or restart cannot repeat the slot
                    fn()
            t = time.gmtime(now)
            if t.tm_hour == 1 and t.tm_yday != last_day:
                last_day = t.tm_yday
                bot.daily_summary()
        except Exception as e:
            log.error("loop error: %s", notify.redact(f"{type(e).__name__}: {e}"))
            notify.send(f"⚠️ Lỗi vòng lặp: {type(e).__name__}: {e}"[:300])
        time.sleep(20)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for name in ("httpx", "httpx2"):   # request log lines contain URLs; the Discord webhook URL carries its token
        logging.getLogger(name).setLevel(logging.WARNING)
    mode = os.getenv("MODE", "paper")
    if mode not in ("paper", "demo", "live"):
        sys.exit(f"MODE must be paper, demo or live, got {mode!r}")
    if mode == "live" and os.getenv("LIVE_CONFIRM") != "I-ACCEPT-REAL-MONEY":
        sys.exit("MODE=live needs LIVE_CONFIRM=I-ACCEPT-REAL-MONEY")
    store = Store(os.getenv("DB_PATH", "data/bot.db"))
    if "--clear-halt" in sys.argv:
        store.log("halt_clear")
        print("halt cleared")
        return
    strategy = os.getenv("STRATEGY", "v1")
    if strategy not in ("v1", "v2"):
        sys.exit(f"STRATEGY must be v1 or v2, got {strategy!r}")
    if strategy == "v2":
        if mode != "paper":
            sys.exit("STRATEGY=v2 runs in MODE=paper only until the owner gives a separate go for live")
        return run_v2(mode, store)
    limits = Limits(leverage=int(os.getenv("LEVERAGE", "5")), risk_pct=float(os.getenv("RISK_PCT", "0.02")),
                    floor_equity=float(os.getenv("FLOOR_EQUITY", "70")))
    ex = make_ccxt(mode)
    on_close = lambda **t: (store.log("trade_close", **t),
                            notify.closed(t["symbol"], t["pnl"], t["why"], t.get("r")))
    broker = (Paper(ex, limits.leverage, float(os.getenv("PAPER_START", "100")), on_close,
                    state=store.last("paper_state"), save=lambda st: store.log("paper_state", **st))
              if mode == "paper" else Binance(ex, SYMBOLS, limits.leverage))
    bot = Bot(broker, LLM(), store, limits, mode)
    sync_last: dict = {}
    if mode != "paper":
        broker.after_order = lambda s: sync.sync_fills(ex, store.db, [s], sync.bot_start_ms())
    if "--once" in sys.argv:
        bot.cycle()
        return
    notify.started([f"**Chế độ:** {'tiền thật' if mode == 'live' else mode}", f"**Model AI:** {bot.llm.model}",
                     f"**Cặp:** {', '.join(notify.coin(x) for x in SYMBOLS)}"])
    last_day = None
    while True:
        try:
            broker.tick()
            bot.reconcile(broker.positions())        # live/demo: protection checked every 20 s, also right after start
            if mode != "paper":
                sync.run(ex, store.db, SYMBOLS, sync_last)
            now = time.time()
            hour_key = time.strftime("%Y-%m-%dT%H", time.gmtime(now))
            done = store.last("cycle")
            # once per UTC hour, at least 5 s after the candle closes; persisted so a restart cannot repeat it
            if (not done or done["hour"] != hour_key) and now % 3600 >= 5:
                store.log("cycle", hour=hour_key)
                bot.cycle()
            t = time.gmtime(now)
            if t.tm_hour == 1 and t.tm_yday != last_day:   # 01:00 UTC = 08:00 Asia/Ho_Chi_Minh
                last_day = t.tm_yday
                bot.daily_summary()
        except Exception as e:
            log.error("loop error: %s", notify.redact(f"{type(e).__name__}: {e}"))
            notify.send(f"⚠️ Lỗi vòng lặp: {type(e).__name__}: {e}"[:300])
        time.sleep(20)


if __name__ == "__main__":
    main()
