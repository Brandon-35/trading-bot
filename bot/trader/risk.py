"""Pure risk rules. Every order the bot sends passes through these functions first."""
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class Limits:
    risk_pct: float = 0.02          # equity lost if the stop is hit
    leverage: int = 5               # isolated leverage cap
    max_positions: int = 2
    daily_stop_pct: float = 0.06    # pause until next UTC day
    floor_equity: float = 70.0      # full stop until cleared by hand
    min_confidence: float = 0.6
    min_rr: float = 1.5
    sl_min_atr: float = 0.5
    sl_min_pct: float = 0.008       # below this, fees eat more than ~0.12 R
    sl_max_atr: float = 3.0

    def __post_init__(self):
        # hard ceilings; 10 % risk is the owner's decision of 2026-11-28 (D14), above that is a plan change
        if not 0 < self.risk_pct <= 0.10:
            raise ValueError("risk_pct must be in (0, 0.10]")
        if not 1 <= self.leverage <= 10:
            raise ValueError("leverage must be in [1, 10]")


def validate(action: str, price: float, stop_loss: float | None, take_profit: float | None,
             confidence: float, atr: float, limits: Limits) -> str | None:
    """Return a rejection reason for an entry, or None if the entry is acceptable."""
    if action not in ("long", "short"):
        return f"not an entry: {action}"
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (price, atr, confidence)):
        return "non-finite market data"
    if confidence < limits.min_confidence:
        return f"confidence {confidence:.2f} < {limits.min_confidence}"
    if not stop_loss or not take_profit or not math.isfinite(stop_loss) or not math.isfinite(take_profit) \
            or stop_loss <= 0 or take_profit <= 0:
        return "missing stop_loss or take_profit"
    sign = 1 if action == "long" else -1
    risk = (price - stop_loss) * sign
    reward = (take_profit - price) * sign
    if risk <= 0:
        return "stop_loss on the wrong side of price"
    if reward <= 0:
        return "take_profit on the wrong side of price"
    min_dist = max(limits.sl_min_atr * atr, limits.sl_min_pct * price)
    if risk < min_dist:
        return f"stop too tight: {risk:.6g} < {min_dist:.6g}"
    if risk > limits.sl_max_atr * atr:
        return f"stop too wide: {risk:.6g} > {limits.sl_max_atr * atr:.6g}"
    liq = price * (1 / limits.leverage - 0.005)   # isolated liquidation distance, 0.5 % maintenance margin
    if risk * 2 > liq:
        return f"liquidation too close at {limits.leverage}x: stop {risk:.6g} > half of {liq:.6g}"
    if reward / risk < limits.min_rr:
        return f"reward/risk {reward / risk:.2f} < {limits.min_rr}"
    return None


def size(equity: float, free_margin: float, price: float, stop_loss: float,
         step: float, min_qty: float, min_notional: float, limits: Limits) -> tuple[float, str | None]:
    """Quantity that loses `risk_pct` of equity at the stop, rounded down to the lot step.

    Returns (qty, None) or (0, reason)."""
    risk_usdt = equity * limits.risk_pct
    raw = risk_usdt / abs(price - stop_loss)
    # cap so the margin fits with a 5 % buffer for fees: notional / leverage <= 0.95 * free margin
    raw = min(raw, 0.95 * free_margin * limits.leverage / price)
    qty = float((Decimal(str(raw)) / Decimal(str(step))).to_integral_value(ROUND_DOWN) * Decimal(str(step)))
    if qty < min_qty:
        return 0.0, f"qty {qty} < min qty {min_qty}"
    if qty * price < min_notional:
        return 0.0, f"notional {qty * price:.2f} < min notional {min_notional}"
    return qty, None


def halt_reason(equity: float, day_start_equity: float, limits: Limits) -> str | None:
    """'floor' = full stop, 'daily' = pause until next UTC day, None = trade."""
    if equity < limits.floor_equity:
        return "floor"
    if day_start_equity > 0 and (day_start_equity - equity) / day_start_equity >= limits.daily_stop_pct:
        return "daily"
    return None


# ---- v2 (paper arms first; live needs the owner's separate go) -------------------------------------------------

@dataclass(frozen=True)
class V2Limits:
    risk_pct: float = 0.02           # hard cap until the edge gate passes
    risk_pct_proven: float = 0.03    # after >= edge_min_trades closed trades with avg net R >= edge_min_avg_r
    edge_min_trades: int = 30
    edge_min_avg_r: float = 0.10
    max_total_risk: float = 0.10     # sum of open (qty * stop distance) / base, incl. the new trade
    max_positions: int = 3
    max_same_side: int = 2
    max_entries_day: int = 6
    daily_stop_pct: float = 0.12
    floor_equity: float = 12.0
    max_leverage: int = 10
    maint_margin: float = 0.005      # rough maintenance margin rate used for the liquidation estimate
    liq_mult: float = 2.0            # liquidation must be >= liq_mult * stop distance away
    min_notional: float = 5.0        # never below this, even when the market says less
    sl_min_pct: float = 0.008        # a stop closer than this loses too much to fees (same floor as v1)

    def __post_init__(self):
        if not 0 < self.risk_pct <= 0.02:
            raise ValueError("risk_pct must be in (0, 0.02]")
        if not self.risk_pct <= self.risk_pct_proven <= 0.03:
            raise ValueError("risk_pct_proven must be in [risk_pct, 0.03]")
        if not 1 <= self.max_leverage <= 10:
            raise ValueError("max_leverage must be in [1, 10]")


def floor_step(x: float, step: float) -> float:
    return float((Decimal(str(x)) / Decimal(str(step))).to_integral_value(ROUND_DOWN) * Decimal(str(step)))


def edge_proven(rs: list[float], lim: V2Limits) -> bool:
    return len(rs) >= lim.edge_min_trades and sum(rs) / len(rs) >= lim.edge_min_avg_r


def risk_pct(rs: list[float], lim: V2Limits) -> float:
    """rs = this arm's closed-trade net R, oldest first. 2 % until the edge gate passes; halved while the
    last two trades were both losses (a win restores it)."""
    pct = lim.risk_pct_proven if edge_proven(rs, lim) else lim.risk_pct
    return pct / 2 if len(rs) >= 2 and rs[-1] < 0 and rs[-2] < 0 else pct


def size_v2(base: float, rpct: float, stop_dist: float, price: float, step: float, min_qty: float,
            min_notional: float, lim: V2Limits) -> tuple[float, str | None]:
    """Quantity that loses rpct of base at the stop, rounded DOWN; too small is rejected, never rounded up."""
    if not all(math.isfinite(v) and v > 0 for v in (base, rpct, stop_dist, price, step)):
        return 0.0, "bad sizing input"
    qty = floor_step(base * rpct / stop_dist, step)
    if qty < max(min_qty, step):
        return 0.0, f"qty {qty} < min qty {max(min_qty, step)}"
    need = max(min_notional, lim.min_notional)
    if qty * price < need:
        return 0.0, f"notional {qty * price:.2f} < min notional {need}"
    return qty, None


def open_risk(side: str, qty: float, entry: float, stop: float) -> float:
    """USDT lost if the stop hits; a stop already beyond breakeven risks nothing."""
    return max(0.0, (entry - stop if side == "long" else stop - entry) * qty)


def check_caps(positions: list[dict], side: str, new_risk: float, entries_today: int, base: float,
               lim: V2Limits) -> str | None:
    """positions: [{side, risk}] of the bot's open positions (without the new one)."""
    if len(positions) >= lim.max_positions:
        return "max positions reached"
    if sum(p["side"] == side for p in positions) >= lim.max_same_side:
        return f"max {lim.max_same_side} {side} positions"
    if entries_today >= lim.max_entries_day:
        return "max entries per day reached"
    total = sum(p["risk"] for p in positions) + new_risk
    if total > lim.max_total_risk * base + 1e-9:
        return f"total open risk {total:.2f} > {lim.max_total_risk:.0%} of base"
    return None


def pick_leverage(notional: float, margin_avail: float, entry: float, stop_dist: float,
                  lim: V2Limits) -> tuple[int | None, str | None]:
    """Smallest integer leverage whose margin fits (5 % fee buffer) and whose estimated liquidation
    (entry * (1/L - maintenance rate)) is >= liq_mult * stop distance away; None + reason if there is none."""
    if margin_avail <= 0:
        return None, "no free margin"
    for lev in range(1, lim.max_leverage + 1):
        if notional / lev > 0.95 * margin_avail:
            continue
        if entry * (1 / lev - lim.maint_margin) >= lim.liq_mult * stop_dist:
            return lev, None
        return None, f"liquidation too close at {lev}x (need >= {lim.liq_mult}x the stop distance)"
    return None, f"notional {notional:.2f} needs more than {lim.max_leverage}x for {margin_avail:.2f} margin"
