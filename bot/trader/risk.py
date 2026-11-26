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
        # hard ceilings from the approved plan; raising them is a plan change, not an env tweak
        if not 0 < self.risk_pct <= 0.02:
            raise ValueError("risk_pct must be in (0, 0.02]")
        if not 1 <= self.leverage <= 5:
            raise ValueError("leverage must be in [1, 5]")


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
