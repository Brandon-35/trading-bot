"""AC1: signed read with the live key from this host, and the key's permissions. Places no order.

    BINANCE_API_KEY=... BINANCE_API_SECRET=... python -m trader.key_check
"""
import os
import sys

import ccxt


def main():
    ex = ccxt.binanceusdm({"apiKey": os.environ["BINANCE_API_KEY"], "secret": os.environ["BINANCE_API_SECRET"]})
    bal = ex.fetch_balance().get("USDT") or {}   # absent while the futures wallet is empty
    print(f"PASS signed fetch_balance: USDT total={bal.get('total')} free={bal.get('free')}")
    r = ccxt.binance({"apiKey": os.environ["BINANCE_API_KEY"],
                      "secret": os.environ["BINANCE_API_SECRET"]}).sapi_get_account_apirestrictions()
    keys = ("ipRestrict", "enableWithdrawals", "enableFutures", "enableReading")
    print("restrictions:", {k: r.get(k) for k in keys})
    ok = r.get("ipRestrict") is True and r.get("enableWithdrawals") is False and r.get("enableFutures") is True
    print(("PASS" if ok else "FAIL") + " key is IP-restricted, cannot withdraw, can trade futures")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
