"""Two brokers with one interface: Binance (live or demo) and a paper simulator on live prices.

Interface: equity(), free_margin(), positions() -> {symbol: {side, qty, entry}},
protective_count(symbol), open(symbol, side, qty, sl, tp), close(symbol), cancel_protective(symbol),
tick() (paper only: fills stops), market(symbol) -> ccxt market dict, data = ccxt instance for prices.
"""
import logging
import os
import time

import ccxt

from .sync import PREFIX, cid

log = logging.getLogger("exchange")


def make_ccxt(mode: str) -> ccxt.binanceusdm:
    if mode == "paper":
        return ccxt.binanceusdm({"enableRateLimit": True})   # public data only, no keys
    if not (os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET")):
        raise SystemExit(f"MODE={mode} needs BINANCE_API_KEY and BINANCE_API_SECRET")
    ex = ccxt.binanceusdm({"apiKey": os.environ["BINANCE_API_KEY"], "secret": os.environ["BINANCE_API_SECRET"],
                           "enableRateLimit": True})
    if mode == "demo":
        ex.enable_demo_trading(True)
    return ex


class Binance:
    def __init__(self, ex: ccxt.binanceusdm, symbols: list[str], leverage: int):
        self.data = self.ex = ex
        self.after_order = lambda symbol: None   # main sets it: sync fills so ownership is known right away
        ex.load_markets()
        # setup must never block startup (e.g. a position is already open): reconcile has to run
        for call, args in [(ex.set_position_mode, (False,))] + \
                [(f, a) for s in symbols for f, a in ((ex.set_margin_mode, ("isolated", s)), (ex.set_leverage, (leverage, s)))]:
            try:
                call(*args)
            except ccxt.ExchangeError as e:
                log.warning("setup %s%s: %s", call.__name__, args, str(e)[:200])

    def market(self, symbol):
        return self.ex.market(symbol)

    def _balance(self):
        return self.ex.fetch_balance().get("USDT") or {"total": 0, "free": 0}   # absent while the wallet is empty

    def equity(self) -> float:
        info = self.ex.fetch_balance()["info"]
        return float(info.get("totalMarginBalance") or self._balance()["total"] or 0)

    def free_margin(self) -> float:
        return float(self._balance()["free"] or 0)

    def positions(self) -> dict:
        out = {}
        for p in self.ex.fetch_positions():
            if float(p.get("contracts") or 0) > 0:
                out[p["symbol"]] = {"side": p["side"], "qty": float(p["contracts"]), "entry": float(p["entryPrice"])}
        return out

    def _bot_triggers(self, symbol) -> list:
        """Only the bot's own trigger orders; the owner's hand-placed stops are never counted or cancelled."""
        return [o for o in self.ex.fetch_open_orders(symbol, params={"trigger": True}) if cid(o).startswith(PREFIX)]

    def protective_count(self, symbol) -> int:
        return len(self._bot_triggers(symbol))

    def cancel_protective(self, symbol):
        for o in self._bot_triggers(symbol):
            self.ex.cancel_order(o["id"], symbol, {"trigger": True})

    def _synced(self, symbol):
        try:
            self.after_order(symbol)
        except Exception as e:
            log.warning("fill sync %s: %s", symbol, type(e).__name__)

    def open(self, symbol, side, qty, sl, tp):
        """Market entry, then SL and TP. Any failure (even an ambiguous entry timeout) flattens and re-raises."""
        buy = side == "long"
        self.cancel_protective(symbol)                       # no orphan reduce-only order may hit the new position
        exit_side = "sell" if buy else "buy"
        try:
            order = self.ex.create_order(symbol, "market", "buy" if buy else "sell", qty)
            # shortcut: quantity + reduceOnly, not closePosition; the sibling of a filled stop is cancelled by
            # reconcile within ~20 s. Switch to closePosition once it is verified on the algo endpoint.
            for key, px in (("stopLossPrice", sl), ("takeProfitPrice", tp)):
                self.ex.create_order(symbol, "market", exit_side, qty, None,
                                     {key: self.ex.price_to_precision(symbol, px), "reduceOnly": True,
                                      "workingType": "MARK_PRICE"})
        except Exception:
            self._flatten(symbol, exit_side, qty)
            raise
        self._synced(symbol)
        return order

    def _flatten(self, symbol, exit_side, qty):
        """Reduce-only market exit with the known qty; Binance rejects it if already flat, so retrying is safe."""
        for attempt in range(3):
            try:
                self.ex.create_order(symbol, "market", exit_side, qty, None, {"reduceOnly": True})
                break
            except Exception:
                if attempt == 2 or not self.positions().get(symbol):
                    break
                time.sleep(1)
        if not self.positions().get(symbol):
            self.cancel_protective(symbol)
        self._synced(symbol)

    def close(self, symbol):
        """Exit first, cancel protection second, so a failed exit never leaves a naked position."""
        p = self.positions().get(symbol)
        if p:
            self.ex.create_order(symbol, "market", "sell" if p["side"] == "long" else "buy", p["qty"], None,
                                 {"reduceOnly": True})
        self.cancel_protective(symbol)
        self._synced(symbol)

    def tick(self):
        pass


class Paper:
    """Fills at the live last price with slippage and taker fee; stops checked on 1m candles (stop wins a tie)."""
    FEE, SLIP = 0.0005, 0.0002

    def __init__(self, ex: ccxt.binanceusdm, leverage: int, start: float = 100.0, on_close=None,
                 state: dict | None = None, save=None):
        """`state` is the last saved {cash, pos, last_funding_hour}; `save(state)` persists it."""
        self.data = ex
        ex.load_markets()
        s = state or {}
        self.leverage = leverage
        self.cash, self.pos = s.get("cash", start), s.get("pos", {})
        self.last_funding_hour = tuple(s["last_funding_hour"]) if s.get("last_funding_hour") else None
        self.on_close = on_close or (lambda **k: None)
        self.save = save or (lambda st: None)

    def _save(self):
        self.save({"cash": self.cash, "pos": self.pos, "last_funding_hour": self.last_funding_hour})

    def market(self, symbol):
        return self.data.market(symbol)

    def _px(self, symbol):
        return float(self.data.fetch_ticker(symbol)["last"])

    def _upnl(self, p, px):
        return (px - p["entry"]) * p["qty"] * (1 if p["side"] == "long" else -1)

    def equity(self):
        return self.cash + sum(self._upnl(p, self._px(s)) for s, p in self.pos.items())

    def free_margin(self):
        used = sum(p["entry"] * p["qty"] / self.leverage for p in self.pos.values())
        return self.equity() - used

    def positions(self):
        return {s: {k: p[k] for k in ("side", "qty", "entry")} for s, p in self.pos.items()}

    def protective_count(self, symbol):
        return 2 if symbol in self.pos else 0

    def cancel_protective(self, symbol):
        pass

    def open(self, symbol, side, qty, sl, tp):
        px = self._px(symbol) * (1 + self.SLIP if side == "long" else 1 - self.SLIP)
        self.cash -= px * qty * self.FEE
        self.pos[symbol] = {"side": side, "qty": qty, "entry": px, "sl": sl, "tp": tp,
                            "fees": px * qty * self.FEE, "funding": 0.0, "opened": int(time.time() * 1000)}
        self._save()

    def _exit(self, symbol, px, why):
        p = self.pos.pop(symbol)
        px *= (1 - self.SLIP if p["side"] == "long" else 1 + self.SLIP)
        fee = px * p["qty"] * self.FEE
        pnl = self._upnl(p, px)
        self.cash += pnl - fee
        self._save()
        self.on_close(symbol=symbol, side=p["side"], qty=p["qty"], entry=p["entry"], exit=px, why=why,
                      pnl=pnl - fee - p["fees"] + p["funding"], fees=fee + p["fees"], funding=p["funding"])

    def close(self, symbol):
        if symbol in self.pos:
            self._exit(symbol, self._px(symbol), "close")

    def tick(self):
        """Call about once a minute: fill stops hit since the last check, apply funding at 00/08/16 UTC."""
        now = int(time.time() * 1000)
        for s in list(self.pos):
            p = self.pos[s]
            first = p["opened"] // 60_000 * 60_000 + 60_000      # first full minute after the entry
            # re-scan the last 1000 minutes every tick: idempotent, survives restarts; an outage > 16 h may miss stops
            for c in self.data.fetch_ohlcv(s, "1m", since=max(now - 999 * 60_000, first), limit=1000):
                op, hi, lo = c[1], c[2], c[3]
                long = p["side"] == "long"
                hit_sl = lo <= p["sl"] if long else hi >= p["sl"]
                hit_tp = hi >= p["tp"] if long else lo <= p["tp"]
                if hit_sl:   # a stop-market fills at the open when the candle gaps through it
                    self._exit(s, min(op, p["sl"]) if long else max(op, p["sl"]), "stop_loss")
                    break
                if hit_tp:
                    self._exit(s, p["tp"], "take_profit")
                    break
        hour = time.gmtime(now / 1000)
        key = (hour.tm_yday, hour.tm_hour)
        # shortcut: assumes 8h funding (true for BTC/ETH; SOL may be 4h), read fundingInterval if more symbols are added
        if hour.tm_hour % 8 == 0 and key != self.last_funding_hour:
            self.last_funding_hour = key
            for s, p in self.pos.items():
                rate = float(self.data.fetch_funding_rate(s).get("fundingRate") or 0)
                pay = p["entry"] * p["qty"] * rate * (1 if p["side"] == "long" else -1)
                p["funding"] -= pay
                self.cash -= pay
            self._save()
