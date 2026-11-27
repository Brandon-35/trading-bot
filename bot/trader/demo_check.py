"""Order-path checks with fixed decisions, no LLM. Covers plan AC5-AC7.

    MODE=demo|live BINANCE_API_KEY=... BINANCE_API_SECRET=... python -m trader.demo_check
On live this trades ~12 USDT SOL notional for real; expected cost a few cents (fees + one tight stop).
"""
import os
import sys
import time

from .exchange import Binance, make_ccxt
from .main import SYMBOLS, Bot
from .risk import Limits
from .store import Store

S = "SOL/USDT:USDT"


def say(ok: bool, what: str):
    print(("PASS " if ok else "FAIL ") + what, flush=True)
    return ok


def main():
    mode = os.getenv("MODE")
    if mode not in ("demo", "live") or mode == "live" and os.getenv("LIVE_CONFIRM") != "I-ACCEPT-REAL-MONEY":
        sys.exit("demo_check needs MODE=demo, or MODE=live with LIVE_CONFIRM=I-ACCEPT-REAL-MONEY")
    ex = make_ccxt(mode)
    b = Binance(ex, SYMBOLS, 5)
    bot = Bot(b, None, Store("/tmp/demo_check.db"), Limits(), mode)
    results = []
    px = float(ex.fetch_ticker(S)["last"])
    qty = float(ex.amount_to_precision(S, 12 / px))            # ~12 USDT notional

    # AC5a: entry -> position + 2 protective orders, still protected after a reconcile 70 s later
    b.open(S, "long", qty, px * 0.97, px * 1.05)
    time.sleep(3)
    results.append(say(S in b.positions() and b.protective_count(S) == 2, "AC5a entry has position + SL + TP"))
    time.sleep(70)
    bot.reconcile(b.positions())
    results.append(say(S in b.positions() and b.protective_count(S) == 2, "AC5a still open and protected after reconcile"))

    # AC7: a fresh broker (restart) with the position open must start and reconcile without a duplicate entry
    b2 = Binance(make_ccxt(mode), SYMBOLS, 5)
    Bot(b2, None, Store("/tmp/demo_check.db"), Limits(), mode).reconcile(b2.positions())
    p = b2.positions().get(S)
    results.append(say(bool(p) and abs(p["qty"] - qty) < 1e-9 and b2.protective_count(S) == 2,
                       "AC7 restart keeps one position with its SL/TP"))
    b.close(S)
    time.sleep(2)
    results.append(say(S not in b.positions() and b.protective_count(S) == 0, "close leaves no position and no orders"))

    # AC5b: stop fills -> sibling TP is gone after reconcile
    px = float(ex.fetch_ticker(S)["last"])
    b.open(S, "long", qty, px * 0.9985, px * 1.05)          # 0.15 % stop, should trigger within minutes
    for _ in range(60):                                      # up to 10 min
        time.sleep(10)
        if S not in b.positions():
            break
    bot.reconcile(b.positions())
    results.append(say(S not in b.positions() and b.protective_count(S) == 0, "AC5b stop filled, sibling TP cancelled"))
    b.close(S)

    # AC6: protective order rejected (stop above price for a long) -> flattened, exception raised
    px = float(ex.fetch_ticker(S)["last"])
    try:
        b.open(S, "long", qty, px * 1.02, px * 1.05)
        raised = False
    except Exception as e:
        raised = True
        print("  rejected as expected:", type(e).__name__, str(e)[:150])
    time.sleep(2)
    results.append(say(raised and S not in b.positions() and b.protective_count(S) == 0,
                       "AC6 failed SL placement flattens the position"))
    b.close(S)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
