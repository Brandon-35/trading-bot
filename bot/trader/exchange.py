"""Two brokers with one interface: Binance (live or demo) and a paper simulator on live prices.

Interface: equity(), free_margin(), positions() -> {symbol: {side, qty, entry}},
protective_count(symbol), open(symbol, side, qty, sl, tp), close(symbol), cancel_protective(symbol),
tick() (paper only: fills stops), market(symbol) -> ccxt market dict, data = ccxt instance for prices.
"""
import os
import time

import ccxt


def make_ccxt(mode: str) -> ccxt.binanceusdm:
    if mode == "paper":
        return ccxt.binanceusdm({"enableRateLimit": True})   # public data only, no keys
    ex = ccxt.binanceusdm({"apiKey": os.environ["BINANCE_API_KEY"], "secret": os.environ["BINANCE_API_SECRET"],
                           "enableRateLimit": True})
    if mode == "demo":
        ex.enable_demo_trading(True)
    return ex


class Binance:
    def __init__(self, ex: ccxt.binanceusdm, symbols: list[str], leverage: int):
        self.data = self.ex = ex
        ex.load_markets()
        try:
            ex.set_position_mode(False)                      # one-way
        except ccxt.ExchangeError as e:
            if "-4059" not in str(e):                        # -4059: already one-way
                raise
        for s in symbols:
            try:
                ex.set_margin_mode("isolated", s)
            except ccxt.ExchangeError as e:
                if "-4046" not in str(e):                    # -4046: already isolated
                    raise
            ex.set_leverage(leverage, s)

    def market(self, symbol):
        return self.ex.market(symbol)

    def _balance(self):
        return self.ex.fetch_balance()["USDT"]

    def equity(self) -> float:
        info = self.ex.fetch_balance()["info"]
        return float(info.get("totalMarginBalance") or self._balance()["total"])

    def free_margin(self) -> float:
        return float(self._balance()["free"])

    def positions(self) -> dict:
        out = {}
        for p in self.ex.fetch_positions():
            if float(p.get("contracts") or 0) > 0:
                out[p["symbol"]] = {"side": p["side"], "qty": float(p["contracts"]), "entry": float(p["entryPrice"])}
        return out

    def protective_count(self, symbol) -> int:
        return len(self.ex.fetch_open_orders(symbol, params={"trigger": True}))

    def cancel_protective(self, symbol):
        if self.protective_count(symbol):
            self.ex.cancel_all_orders(symbol, params={"trigger": True})

    def open(self, symbol, side, qty, sl, tp):
        """Market entry, then SL and TP. If either protective order fails, flatten and re-raise."""
        buy = side == "long"
        self.cancel_protective(symbol)                       # no orphan reduce-only order may hit the new position
        order = self.ex.create_order(symbol, "market", "buy" if buy else "sell", qty)
        exit_side = "sell" if buy else "buy"
        try:
            for key, px in (("stopLossPrice", sl), ("takeProfitPrice", tp)):
                self.ex.create_order(symbol, "market", exit_side, qty, None,
                                     {key: self.ex.price_to_precision(symbol, px), "reduceOnly": True,
                                      "workingType": "MARK_PRICE"})
        except Exception:
            self.close(symbol)
            raise
        return order

    def close(self, symbol):
        self.cancel_protective(symbol)
        p = self.positions().get(symbol)
        if p:
            self.ex.create_order(symbol, "market", "sell" if p["side"] == "long" else "buy", p["qty"], None,
                                 {"reduceOnly": True})

    def tick(self):
        pass


class Paper:
    """Fills at the live last price with slippage and taker fee; stops checked on 1m candles (stop wins a tie)."""
    FEE, SLIP = 0.0005, 0.0002

    def __init__(self, ex: ccxt.binanceusdm, leverage: int, start: float = 100.0, on_close=None):
        self.data = ex
        ex.load_markets()
        self.leverage, self.cash, self.pos = leverage, start, {}
        self.last_check = int(time.time() * 1000)
        self.last_funding_hour = None
        self.on_close = on_close or (lambda **k: None)

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

    def _exit(self, symbol, px, why):
        p = self.pos.pop(symbol)
        px *= (1 - self.SLIP if p["side"] == "long" else 1 + self.SLIP)
        fee = px * p["qty"] * self.FEE
        pnl = self._upnl(p, px)
        self.cash += pnl - fee
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
            for c in self.data.fetch_ohlcv(s, "1m", since=max(self.last_check - 60_000, first), limit=100):
                lo, hi = c[3], c[2]
                hit_sl = lo <= p["sl"] if p["side"] == "long" else hi >= p["sl"]
                hit_tp = hi >= p["tp"] if p["side"] == "long" else lo <= p["tp"]
                if hit_sl or hit_tp:
                    self._exit(s, p["sl"] if hit_sl else p["tp"], "stop_loss" if hit_sl else "take_profit")
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
        self.last_check = now
