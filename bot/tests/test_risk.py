from trader.risk import Limits, halt_reason, size, validate

L = Limits()
ATR = 600.0      # BTC 1h ATR
PRICE = 60_000.0


def test_valid_long_and_short():
    assert validate("long", PRICE, 59_000, 62_000, 0.7, ATR, L) is None
    assert validate("short", PRICE, 61_000, 58_000, 0.7, ATR, L) is None


def test_rejects_missing_or_wrong_side_stop():
    assert "missing" in validate("long", PRICE, None, 62_000, 0.7, ATR, L)
    assert "wrong side" in validate("long", PRICE, 61_000, 62_000, 0.7, ATR, L)
    assert "wrong side" in validate("short", PRICE, 59_000, 58_000, 0.7, ATR, L)
    assert "take_profit" in validate("long", PRICE, 59_000, 59_500, 0.7, ATR, L)


def test_rejects_low_rr_and_confidence_and_non_entry():
    assert "reward/risk" in validate("long", PRICE, 59_000, 61_000, 0.7, ATR, L)  # RR 1.0
    assert "confidence" in validate("long", PRICE, 59_000, 62_000, 0.5, ATR, L)
    assert "not an entry" in validate("hold", PRICE, None, None, 0.9, ATR, L)


def test_stop_floor_and_ceiling():
    # 0.5*ATR = 300 but 0.8 % of price = 480 wins -> 400 away is too tight
    assert "too tight" in validate("long", PRICE, 59_600, 61_000, 0.7, ATR, L)
    # 3*ATR = 1800 -> 2000 away is too wide
    assert "too wide" in validate("long", PRICE, 58_000, 66_000, 0.7, ATR, L)


def test_size_risks_two_percent_and_rounds_down():
    qty, why = size(100, 100, PRICE, 59_000, 0.001, 0.001, 50, L)
    assert why is None
    assert qty == 0.002                         # 2 USDT / 1000 = 0.002 BTC
    assert qty * (PRICE - 59_000) <= 100 * L.risk_pct + 1e-9


def test_size_rounds_down_to_step():
    qty, _ = size(100, 100, 150.0, 147.0, 0.01, 0.01, 5, L)   # 2/3 = 0.6666 SOL
    assert qty == 0.66


def test_size_skips_below_min_notional():
    # BTC with a wide stop: 2/1700 = 0.00117 -> 0.001 BTC = 60 USDT < 100 min notional
    qty, why = size(100, 100, PRICE, 58_300, 0.001, 0.001, 100, L)
    assert qty == 0 and "min notional" in why


def test_size_capped_by_free_margin():
    # tiny stop would want a huge position; 10 USDT free * 5x = 50 USDT notional max
    qty, why = size(100, 10, 150.0, 149.0, 0.01, 0.01, 5, L)
    assert why is None and qty * 150.0 <= 10 * L.leverage


def test_halts():
    assert halt_reason(69.9, 80, L) == "floor"
    assert halt_reason(94.0, 100, L) == "daily"
    assert halt_reason(94.1, 100, L) is None
    assert halt_reason(100, 0, L) is None
