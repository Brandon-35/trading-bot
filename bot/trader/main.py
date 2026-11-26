"""Main loop: every minute fill paper stops; on every 1h close ask the LLM and act within the risk rules.

MODE=paper (default) | demo | live. Live also needs LIVE_CONFIRM=I-ACCEPT-REAL-MONEY.
`python -m trader.main --clear-halt` lifts a full stop after the owner has looked at it.
`python -m trader.main --once` runs one decision cycle and exits (smoke test).
"""
import logging
import os
import sys
import time

from . import notify
from .exchange import Binance, Paper, make_ccxt
from .llm import LLM
from .market import snapshot
from .risk import Limits, halt_reason, size, validate
from .store import Store

log = logging.getLogger("bot")
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT").split(",")


def halted(store: Store) -> bool:
    q = "SELECT COALESCE(MAX(rowid), 0) FROM events WHERE kind = ?"
    return store.db.execute(q, ("halt",)).fetchone()[0] > store.db.execute(q, ("halt_clear",)).fetchone()[0]


class Bot:
    def __init__(self, broker, llm, store: Store, limits: Limits, mode: str):
        self.broker, self.llm, self.store, self.limits, self.mode = broker, llm, store, limits, mode

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
        for s in set(SYMBOLS) | set(positions):
            n = self.broker.protective_count(s)
            if s in positions and n < 2:
                self.broker.close(s)
                self.store.log("reconcile_close", symbol=s, protective=n)
                notify.send(f"⚠️ {s}: position had {n}/2 protective orders, closed at market")
            elif s not in positions and n:
                self.broker.cancel_protective(s)
                self.store.log("reconcile_cancel", symbol=s, orders=n)

    def cycle(self):
        if halted(self.store):
            log.info("halted, waiting for --clear-halt")
            return
        positions = self.broker.positions()
        self.reconcile(positions)
        positions = self.broker.positions()
        equity = self.broker.equity()
        day_start = self.day_start_equity(equity)
        self.store.log("equity", equity=equity, positions=positions)
        stop = halt_reason(equity, day_start, self.limits)
        if stop == "floor":
            for s in list(positions):
                self.broker.close(s)
            self.store.log("halt", equity=equity)
            notify.send(f"🛑 FULL STOP: equity {equity:.2f} < {self.limits.floor_equity}. All positions closed. "
                        "Run `python -m trader.main --clear-halt` to resume.")
            return

        snap, ref = snapshot(self.broker.data, SYMBOLS)
        decisions, meta = self.llm.decide({"time_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
                                           "equity": round(equity, 2), "open_positions": positions, "symbols": snap})
        self.store.log("llm_call", **meta)
        if "error" in meta:
            notify.send(f"LLM error, holding: {meta['error'][:200]}")

        for d in decisions:
            reason = self.act(d, positions, ref, equity, stop)
            self.store.log("decision", **d.model_dump(), accepted=reason is None, reject=reason)
            positions = self.broker.positions()

    def act(self, d, positions, ref, equity, stop) -> str | None:
        if d.symbol not in SYMBOLS:
            return "symbol not allowed"
        if d.action == "hold":
            return None
        if d.action == "close":
            if d.symbol not in positions:
                return "no position to close"
            self.broker.close(d.symbol)
            notify.send(f"close {d.symbol}: {d.reason}")
            return None
        if stop == "daily":
            return "daily loss stop active"
        if d.symbol in positions:
            return "position already open"
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
            notify.send(f"⚠️ {d.symbol} entry failed, flattened: {type(e).__name__}: {e}"[:300])
            return f"order failed: {type(e).__name__}"
        self.store.log("trade_open", symbol=d.symbol, side=d.action, qty=qty, price=price,
                       sl=d.stop_loss, tp=d.take_profit, confidence=d.confidence)
        notify.send(f"{d.action} {qty} {d.symbol} @~{price} SL {d.stop_loss} TP {d.take_profit} — {d.reason}")
        return None

    def daily_summary(self):
        e = self.store.last("equity") or {}
        cost = self.store.db.execute(
            "SELECT COALESCE(SUM(json_extract(data,'$.cost')),0) FROM events WHERE kind='llm_call'").fetchone()[0]
        notify.send(f"daily: equity {e.get('equity', 0):.2f}, open {list((e.get('positions') or {}))}, "
                    f"LLM cost to date ${cost:.2f}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for name in ("httpx", "httpx2"):   # request log lines contain URLs; the Telegram one carries the token
        logging.getLogger(name).setLevel(logging.WARNING)
    mode = os.getenv("MODE", "paper")
    if mode not in ("paper", "demo", "live"):
        sys.exit(f"MODE must be paper, demo or live, got {mode!r}")
    if mode == "live" and os.getenv("LIVE_CONFIRM") != "I-ACCEPT-REAL-MONEY":
        sys.exit("MODE=live needs LIVE_CONFIRM=I-ACCEPT-REAL-MONEY")
    if not os.getenv("LLM_API_KEY") and "--clear-halt" not in sys.argv:
        sys.exit("LLM_API_KEY is empty")
    store = Store(os.getenv("DB_PATH", "data/bot.db"))
    if "--clear-halt" in sys.argv:
        store.log("halt_clear")
        print("halt cleared")
        return
    limits = Limits(leverage=int(os.getenv("LEVERAGE", "5")), risk_pct=float(os.getenv("RISK_PCT", "0.02")))
    ex = make_ccxt(mode)
    on_close = lambda **t: (store.log("trade_close", **t),
                            notify.send(f"{t['why']} {t['symbol']} pnl {t['pnl']:+.2f}"))
    broker = (Paper(ex, limits.leverage, float(os.getenv("PAPER_START", "100")), on_close,
                    state=store.last("paper_state"), save=lambda st: store.log("paper_state", **st))
              if mode == "paper" else Binance(ex, SYMBOLS, limits.leverage))
    bot = Bot(broker, LLM(), store, limits, mode)
    if "--once" in sys.argv:
        bot.cycle()
        return
    notify.send(f"started mode={mode} model={bot.llm.model} symbols={SYMBOLS}")
    last_day = None
    while True:
        try:
            broker.tick()
            bot.reconcile(broker.positions())        # live/demo: protection checked every 20 s, also right after start
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
            notify.send(f"loop error: {type(e).__name__}: {e}"[:300])
        time.sleep(20)


if __name__ == "__main__":
    main()
