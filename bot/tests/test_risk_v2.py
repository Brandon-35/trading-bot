"""v2 sizing, caps and leverage: pure functions, no exchange."""
import pytest

from trader.risk import (V2Limits, check_caps, edge_proven, open_risk, pick_leverage, risk_pct, size_v2)

L = V2Limits()


def test_risk_is_two_percent_until_the_edge_gate_passes():
    assert risk_pct([], L) == 0.02
    assert risk_pct([0.5] * 29, L) == 0.02                    # 29 trades: not enough evidence
    assert not edge_proven([0.09] * 30, L)                    # 30 trades but avg 0.09 < 0.10
    assert risk_pct([0.5] * 30, L) == 0.03                    # 30 trades, avg 0.5R -> proven


def test_risk_halves_after_two_losses_and_a_win_restores_it():
    assert risk_pct([1, -1], L) == 0.02
    assert risk_pct([1, -1, -1], L) == 0.01
    assert risk_pct([1, -1, -1, -1], L) == 0.01               # stays halved, not quartered
    assert risk_pct([-1, -1, 1], L) == 0.02
    assert risk_pct([0.5] * 30 + [-1, -1], L) == 0.015       # proven 3 % halved


def test_limits_ceilings():
    with pytest.raises(ValueError):
        V2Limits(risk_pct=0.03)
    with pytest.raises(ValueError):
        V2Limits(risk_pct_proven=0.05)
    with pytest.raises(ValueError):
        V2Limits(max_leverage=11)


def test_size_risks_base_times_pct_and_rounds_down():
    qty, why = size_v2(18.7392, 0.02, 0.5, 10.0, 0.1, 0.1, 5, L)   # 0.3748 / 0.5 = 0.7496 -> 0.7
    assert why is None and qty == 0.7
    assert qty * 0.5 <= 18.7392 * 0.02


def test_size_never_rounds_up_to_reach_min_notional():
    # risk 0.37 / 0.5 stop = 0.7 SOL * 6 = 4.2 USDT < 5 -> reject (rounding up would risk more than 2 %)
    qty, why = size_v2(18.7392, 0.02, 0.5, 6.0, 0.1, 0.1, 0, L)
    assert qty == 0 and "min notional" in why
    assert size_v2(100, 0.02, 100.0, 1000.0, 0.001, 0.001, 20, L) == (0.02, None)    # notional exactly 20
    assert "min notional" in size_v2(100, 0.02, 100.0, 1000.0, 0.001, 0.001, 30, L)[1]  # exchange min beats our 5


def test_size_rejects_garbage():
    assert size_v2(float("nan"), 0.02, 1, 1, 0.1, 0.1, 5, L)[0] == 0
    assert size_v2(10, 0.02, 0, 1, 0.1, 0.1, 5, L)[0] == 0


def test_open_risk_is_zero_once_the_stop_is_past_breakeven():
    assert open_risk("long", 2, 100, 95) == 10
    assert open_risk("short", 2, 100, 105) == 10
    assert open_risk("long", 2, 100, 101) == 0
    assert open_risk("short", 2, 100, 99) == 0


def test_caps():
    two_long = [{"side": "long", "risk": 1.0}, {"side": "long", "risk": 1.0}]
    assert "same" in check_caps(two_long, "long", 1.0, 0, 100, L) or "long" in check_caps(two_long, "long", 1.0, 0, 100, L)
    assert check_caps(two_long, "short", 1.0, 0, 100, L) is None             # opposite side still allowed
    three = two_long + [{"side": "short", "risk": 1.0}]
    assert "max positions" in check_caps(three, "short", 1.0, 0, 100, L)
    assert "entries" in check_caps([], "long", 1.0, 6, 100, L)
    assert check_caps([], "long", 1.0, 5, 100, L) is None
    # total risk <= 10 % of base, including the new trade
    pos = [{"side": "long", "risk": 4.0}, {"side": "short", "risk": 4.0}]
    assert check_caps(pos, "long", 2.0, 0, 100, L) is None                   # exactly 10
    assert "total open risk" in check_caps(pos, "long", 2.01, 0, 100, L)


def test_leverage_is_the_smallest_that_fits_the_margin():
    assert pick_leverage(40, 100, 100, 5, L) == (1, None)
    assert pick_leverage(40, 10, 100, 5, L) == (5, None)           # 40/5 = 8 <= 9.5 (4x needs 10 > 9.5)


def test_leverage_rejects_when_liquidation_is_too_close_or_margin_too_small():
    lev, why = pick_leverage(100, 12, 100, 6, L)                   # 9x: liq 10.6 away < 2 x 6
    assert lev is None and "liquidation" in why
    lev, why = pick_leverage(400, 30, 100, 1, L)                   # would need 15x
    assert lev is None and "more than 10x" in why
    assert pick_leverage(10, 0, 100, 1, L)[0] is None
