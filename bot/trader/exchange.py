"""Two brokers with one interface: Binance (live or demo) and a paper simulator on live prices.

Interface: equity(), free_margin(), positions() -> {symbol: {side, qty, entry}},
protective_count(symbol), open(symbol, side, qty, sl, tp), close(symbol), cancel_protective(symbol),
tick() (paper only: fills stops), market(symbol) -> ccxt market dict, data = ccxt instance for prices.
v2 adds open_v2() (maker-first entry, stop for the full qty, TP for half), stop_cover(symbol) and
move_stop(symbol, new_stop, qty); both brokers share these semantics.
"""
import logging
import os
import time

import ccxt

from .risk import floor_step
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


def side_ccxt(buy: bool) -> str:
    return "buy" if buy else "sell"


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

    # ---- v2 -------------------------------------------------------------------------------------------------
    entry_wait, poll = 60.0, 2.0          # seconds the post-only entry may rest before the market fallback
    _sleep = staticmethod(time.sleep)

    @staticmethod
    def _kind(o) -> str:
        i = o.get("info") or {}   # algo (conditional) orders carry orderType, classic ones origType
        return str(i.get("orderType") or i.get("origType") or i.get("type") or o.get("type") or "").upper()

    @staticmethod
    def _amt(o) -> float:
        i = o.get("info") or {}
        return float(o.get("amount") or i.get("origQty") or i.get("quantity") or 0)

    def stop_cover(self, symbol) -> float:
        """Quantity the bot's own stop orders (not take-profits) would close."""
        return sum(self._amt(o) for o in self._bot_triggers(symbol) if self._kind(o).startswith("STOP"))

    def _trigger(self, symbol, exit_side, qty, key, px):
        return self.ex.create_order(symbol, "market", exit_side, qty, None,
                                    {key: self.ex.price_to_precision(symbol, px), "reduceOnly": True,
                                     "workingType": "MARK_PRICE"})

    def move_stop(self, symbol, new_stop, qty):
        """New stop first, old stops cancelled second: the position is never without a stop in between."""
        p = self.positions().get(symbol)
        if not p:
            raise RuntimeError(f"{symbol}: no position to protect")
        old = [o["id"] for o in self._bot_triggers(symbol) if self._kind(o).startswith("STOP")]
        self._trigger(symbol, "sell" if p["side"] == "long" else "buy", qty, "stopLossPrice", new_stop)
        for i in old:
            try:
                self.ex.cancel_order(i, symbol, {"trigger": True})
            except Exception as e:   # a duplicate reduce-only stop is harmless; a missing one is not
                log.warning("cancel old stop %s %s: %s", symbol, i, type(e).__name__)

    def _await_fill(self, symbol, oid) -> float:
        """Poll the resting entry for entry_wait seconds, then cancel it. Returns the filled qty."""
        for _ in range(int(self.entry_wait / self.poll)):
            self._sleep(self.poll)
            o = self.ex.fetch_order(oid, symbol)
            if o.get("status") in ("closed", "canceled", "expired", "rejected"):
                return float(o.get("filled") or 0)
        try:
            self.ex.cancel_order(oid, symbol)
        except Exception as e:               # already filled or gone: the re-read below decides
            log.info("cancel entry %s: %s", symbol, type(e).__name__)
        return float(self.ex.fetch_order(oid, symbol).get("filled") or 0)

    def open_v2(self, symbol, side, qty, sl, tp, setup_price, atr, leverage, tp_frac=0.5):
        """Post-only limit at the best bid/ask for up to entry_wait s; the unfilled rest goes to market only
        while the price is within 0.5 ATR of the setup. Then a stop for the full filled qty and a TP for half.
        Returns {qty, entry, tp_qty, maker} or None when nothing was bought. Any failure flattens and re-raises."""
        buy = side == "long"
        exit_side = "sell" if buy else "buy"
        try:
            self.ex.set_margin_mode("isolated", symbol)
        except ccxt.ExchangeError as e:
            if "-4046" not in str(e) and "No need" not in str(e):
                raise
        self.ex.set_leverage(leverage, symbol)               # the liquidation check relies on it: no swallow
        self.cancel_protective(symbol)
        m = self.market(symbol)
        step, min_qty = m["precision"]["amount"], (m["limits"]["amount"]["min"] or 0)
        oid = None
        try:
            t = self.ex.fetch_ticker(symbol)
            limit = float(self.ex.price_to_precision(symbol, t.get("bid" if buy else "ask") or t["last"]))
            filled = 0.0
            try:
                oid = self.ex.create_order(symbol, "limit", side_ccxt(buy), qty, limit, {"timeInForce": "GTX"})["id"]
            except ccxt.NetworkError:
                raise                                        # ambiguous: the flatten below checks the real position
            except Exception as e:                           # e.g. post-only would cross the book
                log.info("post-only %s rejected: %s", symbol, str(e)[:120])
            if oid:
                filled = self._await_fill(symbol, oid)
            rest = floor_step(qty - filled, step)
            if rest >= max(min_qty, step):
                last = float(self.ex.fetch_ticker(symbol)["last"])
                if abs(last - setup_price) <= 0.5 * atr:
                    self.ex.create_order(symbol, "market", side_ccxt(buy), rest)
            p = self.positions().get(symbol)
            if not p:
                return None
            got = p["qty"]
            tp_qty = floor_step(got * tp_frac, step)
            if tp_qty < max(min_qty, step) or tp_qty >= got:
                tp_qty = 0.0
            self._trigger(symbol, exit_side, got, "stopLossPrice", sl)
            if tp_qty:
                self._trigger(symbol, exit_side, tp_qty, "takeProfitPrice", tp)
        except Exception:
            try:
                if oid:
                    self.ex.cancel_order(oid, symbol)
            except Exception:
                pass
            p = self.positions().get(symbol)
            if p:
                self._flatten(symbol, exit_side, p["qty"])
            raise
        self._synced(symbol)
        return {"qty": got, "entry": p["entry"], "tp_qty": tp_qty, "maker": filled > 0}

    def tick(self):
        pass


class Paper:
    """Fills at the live last price with slippage and taker fee; stops checked on 1m candles (stop wins a tie).

    v2 entries rest as a post-only limit (maker fee, no slippage) and fall back to a taker market fill; the TP can
    close only part of the position, after which the stop is moved by the bot (move_stop). Funding is skipped
    when funding=False (v2 arms)."""
    FEE, MAKER, SLIP = 0.0005, 0.0002, 0.0002
    entry_wait, poll = 60.0, 2.0
    _sleep = staticmethod(time.sleep)

    def __init__(self, ex: ccxt.binanceusdm, leverage: int, start: float = 100.0, on_close=None,
                 state: dict | None = None, save=None, funding: bool = True):
        """`state` is the last saved {cash, pos, last_funding_hour}; `save(state)` persists it."""
        self.data = ex
        ex.load_markets()
        s = state or {}
        self.leverage, self.funding = leverage, funding
        self.cash, self.pos = s.get("cash", start), s.get("pos", {})
        for p in self.pos.values():   # positions saved before v2 had none of these
            for k, v in (("qty0", p["qty"]), ("sl0", p["sl"]), ("tp_qty", p["qty"]), ("realized", 0.0),
                         ("exit_qty", 0.0), ("exit_notional", 0.0), ("seen", 0)):
                p.setdefault(k, v)
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
        used = sum(p["entry"] * p["qty"] / p.get("lev", self.leverage) for p in self.pos.values())
        return self.equity() - used

    def positions(self):
        return {s: {k: p[k] for k in ("side", "qty", "entry")} for s, p in self.pos.items()}

    def protective_count(self, symbol):
        return 2 if symbol in self.pos else 0

    def stop_cover(self, symbol):
        p = self.pos.get(symbol)
        return p["qty"] if p and p.get("sl") else 0.0

    def move_stop(self, symbol, new_stop, qty):
        self.pos[symbol]["sl"] = new_stop
        self._save()

    def cancel_protective(self, symbol):
        pass

    def _new(self, symbol, side, qty, px, fee_rate, sl, tp, tp_qty, lev):
        fee = px * qty * fee_rate
        self.cash -= fee
        self.pos[symbol] = {"side": side, "qty": qty, "qty0": qty, "entry": px, "sl": sl, "sl0": sl, "tp": tp,
                            "tp_qty": tp_qty, "fees": fee, "funding": 0.0, "realized": 0.0, "exit_qty": 0.0,
                            "exit_notional": 0.0, "lev": lev, "seen": 0, "opened": int(time.time() * 1000)}
        self._save()

    def open(self, symbol, side, qty, sl, tp):
        px = self._px(symbol) * (1 + self.SLIP if side == "long" else 1 - self.SLIP)
        self._new(symbol, side, qty, px, self.FEE, sl, tp, qty, self.leverage)

    def open_v2(self, symbol, side, qty, sl, tp, setup_price, atr, leverage, tp_frac=0.5):
        """Same contract as Binance.open_v2: post-only limit that fills when the price touches it, else a taker
        market fill after entry_wait if the price is still within 0.5 ATR of the setup."""
        buy = side == "long"
        t = self.data.fetch_ticker(symbol)
        limit = float(t.get("bid" if buy else "ask") or t["last"])
        px, rate, maker = None, self.FEE, False
        for _ in range(int(self.entry_wait / self.poll)):
            self._sleep(self.poll)
            last = self._px(symbol)
            if (buy and last <= limit) or (not buy and last >= limit):
                px, rate, maker = limit, self.MAKER, True
                break
        if px is None:
            last = self._px(symbol)
            if abs(last - setup_price) > 0.5 * atr:
                return None
            px = last * (1 + self.SLIP if buy else 1 - self.SLIP)
        m = self.market(symbol)
        step, min_qty = m["precision"]["amount"], (m["limits"]["amount"]["min"] or 0)
        tp_qty = floor_step(qty * tp_frac, step)
        if tp_qty < max(min_qty, step) or tp_qty >= qty:
            tp_qty = 0.0
        self._new(symbol, side, qty, px, rate, sl, tp, tp_qty, leverage)
        return {"qty": qty, "entry": px, "tp_qty": tp_qty, "maker": maker}

    def _exit(self, symbol, px, why, qty=None):
        """Exit `qty` (default all) at px with slippage + taker fee. A partial exit keeps the position open;
        the full one logs a single trade_close with net pnl and net R over the whole life of the position."""
        p = self.pos[symbol]
        q = min(qty or p["qty"], p["qty"])
        full = q >= p["qty"] - 1e-12
        px *= (1 - self.SLIP if p["side"] == "long" else 1 + self.SLIP)
        fee = px * q * self.FEE
        gross = (px - p["entry"]) * q * (1 if p["side"] == "long" else -1)
        self.cash += gross - fee
        p["fees"] += fee
        p["exit_qty"] += q
        p["exit_notional"] += px * q
        if not full:
            p["realized"] += gross
            p["qty"] -= q
            self._save()
            return
        del self.pos[symbol]
        self._save()
        net = p["realized"] + gross - p["fees"] + p["funding"]
        risk = p["qty0"] * abs(p["entry"] - p["sl0"])
        self.on_close(symbol=symbol, side=p["side"], qty=p["qty0"], entry=p["entry"],
                      exit=p["exit_notional"] / p["exit_qty"], why=why, pnl=net, fees=p["fees"],
                      funding=p["funding"], r=net / risk if risk > 0 else 0.0)

    def close(self, symbol):
        if symbol in self.pos:
            self._exit(symbol, self._px(symbol), "close")

    def tick(self):
        """Call about once a minute: fill stops hit since the last check, apply funding at 00/08/16 UTC."""
        now = int(time.time() * 1000)
        for s in list(self.pos):
            p = self.pos[s]
            first = p["opened"] // 60_000 * 60_000 + 60_000      # first full minute after the entry
            # re-scan the last 1000 minutes every tick but skip candles already settled (`seen`), so a stop that was
            # moved later never fires on old candles; the still-open candle is looked at again next tick
            for c in self.data.fetch_ohlcv(s, "1m", since=max(now - 999 * 60_000, first), limit=1000):
                if c[0] <= p.get("seen", 0):
                    continue
                op, hi, lo = c[1], c[2], c[3]
                long = p["side"] == "long"
                hit_sl = lo <= p["sl"] if long else hi >= p["sl"]
                hit_tp = p.get("tp_qty", 0) > 0 and (hi >= p["tp"] if long else lo <= p["tp"])
                if hit_sl:   # a stop-market fills at the open when the candle gaps through it
                    self._exit(s, min(op, p["sl"]) if long else max(op, p["sl"]), "stop_loss")
                elif hit_tp:
                    q, p["tp_qty"] = p["tp_qty"], 0.0
                    self._exit(s, p["tp"], "take_profit", q)
                if s not in self.pos:
                    break
                if c[0] + 60_000 <= now:
                    p["seen"] = c[0]
            else:
                self._save()
        hour = time.gmtime(now / 1000)
        key = (hour.tm_yday, hour.tm_hour)
        # shortcut: assumes 8h funding (true for BTC/ETH; SOL may be 4h), read fundingInterval if more symbols are added
        if self.funding and hour.tm_hour % 8 == 0 and key != self.last_funding_hour:
            self.last_funding_hour = key
            for s, p in self.pos.items():
                rate = float(self.data.fetch_funding_rate(s).get("fundingRate") or 0)
                pay = p["entry"] * p["qty"] * rate * (1 if p["side"] == "long" else -1)
                p["funding"] -= pay
                self.cash -= pay
            self._save()
