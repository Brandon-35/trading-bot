"""LLM committee: 3 analysts -> bull/bear -> lead. Runs only when the code engine found a setup. Never raises."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from . import llm

LEAD_MODEL = os.getenv("LEAD_MODEL", "deepseek/deepseek-v3.2")
ANALYST_MODEL = os.getenv("ANALYST_MODEL", "qwen/qwen3-235b-a22b-2507")
MIN_CONFIDENCE = 0.6

_JSON = "Reply with one JSON object only, no prose."
ANALYST_PROMPTS = {
    "technical": "You are the technical analyst of a crypto futures desk. Judge only price action and indicators in the "
                 "setup features (trend, momentum, volatility, levels, BTC trend). ",
    "derivatives": "You are the derivatives/flow analyst of a crypto futures desk. Judge only funding, open interest "
                   "change, long/short ratio and taker flow. If the data is empty, answer neutral with low confidence. ",
    "news": "You are the news/sentiment analyst of a crypto futures desk. Judge only the headlines and the "
            "Fear & Greed index. If nothing relevant, answer neutral with low confidence. ",
}
ANALYST_FORMAT = ('Answer {"stance": "long"|"short"|"neutral", "confidence": 0..1, "key_points": [up to 4 short '
                  'strings]}. ' + _JSON)
BULL_PROMPT = ("You argue FOR taking the proposed trade, using the analyst reports. Be concrete and honest; do not "
               'invent data. Answer {"argument": str (max 120 words), "strongest_point": str}. ' + _JSON)
BEAR_PROMPT = ("You argue AGAINST taking the proposed trade, using the analyst reports. Rebut the bull's strongest "
               'point directly. Do not invent data. Answer {"argument": str (max 120 words), "strongest_point": str}. '
               + _JSON)
LEAD_PROMPT = (
    "You are the lead trader of a small crypto futures account. A rule-based engine proposed one trade; you decide "
    "whether to take it. Default is skip. Open only if the evidence for the setup's side clearly outweighs the bear "
    "case. Side must equal the setup's side, otherwise skip. Analyst disagreement alone is not a reason to skip. "
    "Judge the arguments on substance, independent of speaking order. Never chase a move that already ran. "
    "Weigh the recent closed trades only as context, not as a reason to flip. "
    'Answer {"action": "open"|"skip", "side": "long"|"short", "confidence": 0..1, "sl_atr": stop distance in ATR '
    '(1.0-3.0), "tp_r": take-profit in R multiples (1.5-4.0), "rationale": str (max 60 words)}. ' + _JSON)
MANAGE_PROMPT = (
    "You review one open crypto futures position every hour. You may only hold, tighten the stop (move it closer to "
    "the price, never wider) or close early. Default is hold; close only if the thesis is clearly broken. "
    'Answer {"action": "hold"|"tighten"|"close", "new_stop": number|null, "rationale": str (max 40 words)}. ' + _JSON)


class Analyst(BaseModel):
    stance: Literal["long", "short", "neutral"]
    confidence: float = Field(ge=0, le=1)
    key_points: list[str] = Field(default_factory=list)


class Argument(BaseModel):
    argument: str
    strongest_point: str


class Lead(BaseModel):
    action: Literal["open", "skip"]
    side: Literal["long", "short"]
    confidence: float = Field(ge=0, le=1)
    sl_atr: float
    tp_r: float
    rationale: str


class Manage(BaseModel):
    action: Literal["hold", "tighten", "close"]
    new_stop: float | None = None
    rationale: str = ""


class Budget:
    """Daily LLM spend cap, kept in the store as `llm_cost` events (UTC day)."""

    def __init__(self, store, daily_usd: float | None = None):
        self.store = store
        self.cap = daily_usd if daily_usd is not None else float(os.getenv("LLM_DAILY_USD", "0.10"))

    def spent_today(self) -> float:
        t0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return sum(e.get("usd", 0.0) for e in self.store.all("llm_cost") if e["ts"] >= t0)

    def ok(self) -> bool:
        return self.spent_today() < self.cap


def _round(x):
    if isinstance(x, float):
        return float(f"{x:.5g}")
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    return x


def _dump(x) -> str:
    return json.dumps(_round(x), separators=(",", ":"), default=str)


def _json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(t)


class _Run:
    """Calls the model, logs its cost even when the reply is unusable, and totals the run."""

    def __init__(self, store, chat):
        self.store, self.chat, self.cost = store, chat, 0.0

    def raw(self, model: str, system: str, user: str, max_tokens: int) -> tuple[str, float]:
        return self.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                         max_tokens=max_tokens)

    def parse(self, purpose: str, model: str, res: tuple[str, float], schema):
        text, usd = res
        self.cost += usd
        self.store.log("llm_cost", usd=usd, model=model, purpose=purpose)
        return schema.model_validate(_json(text))

    def ask(self, model: str, purpose: str, system: str, user: str, schema, max_tokens=600):
        return self.parse(purpose, model, self.raw(model, system, user, max_tokens), schema)


def _skip(setup: dict, why: str, cost=0.0, transcript=None) -> dict:
    return {"action": "skip", "side": setup.get("side"), "confidence": 0.0, "sl_atr": 2.0, "tp_r": 2.0,
            "rationale": why, "cost": cost, "transcript": transcript or {}}


def decide(setup: dict, context: dict, recent: list[dict], store, chat=llm.chat) -> dict:
    run = _Run(store, chat)
    transcript: dict = {}
    try:
        if not Budget(store).ok():
            return _skip(setup, "budget")
        base = {"setup": setup, "btc": context.get("btc")}
        views = {"technical": _dump(base),
                 "derivatives": _dump({"symbol": setup["symbol"], "side": setup["side"], "derivs": context.get("derivs") or {}}),
                 "news": _dump({"symbol": setup["symbol"], "side": setup["side"], "headlines": (context.get("news") or [])[:12],
                                "fear_greed": context.get("fear_greed")})}

        def call(name):   # threads only call the model; sqlite writes stay on this thread
            try:
                return name, run.raw(ANALYST_MODEL, ANALYST_PROMPTS[name] + ANALYST_FORMAT, views[name], 400), None
            except Exception as e:
                return name, None, e

        with ThreadPoolExecutor(3) as ex:
            got = list(ex.map(call, ANALYST_PROMPTS))
        analysts = {}
        for name, text, err in got:
            try:   # a missing view is tolerated: the lead sees "unavailable"
                if err:
                    raise err
                analysts[name] = run.parse(f"analyst:{name}", ANALYST_MODEL, text, Analyst).model_dump()
            except Exception as e:
                analysts[name] = {"unavailable": type(e).__name__}
        for a in analysts.values():
            if "key_points" in a:
                a["key_points"] = [str(p) for p in a["key_points"]][:4]
        transcript["analysts"] = analysts
        brief = _dump({"setup": setup, "analysts": analysts})
        bull = run.ask(ANALYST_MODEL, "bull", BULL_PROMPT, brief, Argument, 400)
        bear = run.ask(ANALYST_MODEL, "bear", BEAR_PROMPT, brief + "\nBULL: " + _dump(bull.model_dump()), Argument, 400)
        transcript["bull"], transcript["bear"] = bull.model_dump(), bear.model_dump()
        lead_in = _dump({"setup": setup, "equity": context.get("equity"), "open_positions": context.get("open_positions"),
                         "analysts": analysts, "bull": transcript["bull"], "bear": transcript["bear"],
                         "recent_trades": recent[-10:]})
        lead = run.ask(LEAD_MODEL, "lead", LEAD_PROMPT, lead_in, Lead, 500)
        transcript["lead"] = lead.model_dump()
        res = {"action": lead.action, "side": setup["side"], "confidence": lead.confidence,
               "sl_atr": min(3.0, max(1.0, lead.sl_atr)), "tp_r": min(4.0, max(1.5, lead.tp_r)),
               "rationale": lead.rationale}
        if res["action"] == "open" and lead.side != setup["side"]:
            res.update(action="skip", rationale="lead side != setup side")
        elif res["action"] == "open" and lead.confidence < MIN_CONFIDENCE:
            res.update(action="skip", rationale=f"low confidence {lead.confidence:.2f}: {lead.rationale}")
        res.update(cost=run.cost, transcript=transcript)
    except Exception as e:   # parse, validation, network: skip, never raise
        res = _skip(setup, f"error: {type(e).__name__}", run.cost, transcript)
    res["symbol"] = setup.get("symbol")
    store.log("debate", **res)
    return res


def manage(position: dict, context: dict, store, chat=llm.chat) -> dict:
    """position needs side ('long'|'short'), mark and stop (current stop price); the rest is passed to the model."""
    hold = lambda why: {"action": "hold", "new_stop": None, "rationale": why}   # noqa: E731
    try:
        if not Budget(store).ok():
            return hold("budget")
        user = _dump({"position": position, "btc": context.get("btc"), "derivs": context.get("derivs") or {},
                      "news": (context.get("news") or [])[:8], "fear_greed": context.get("fear_greed")})
        m = _Run(store, chat).ask(ANALYST_MODEL, "manage", MANAGE_PROMPT, user, Manage, 300)
        if m.action == "tighten":
            side, mark, stop = position["side"], position["mark"], position["stop"]
            ok = m.new_stop is not None and (stop < m.new_stop < mark if side == "long" else mark < m.new_stop < stop)
            return {"action": "tighten", "new_stop": m.new_stop, "rationale": m.rationale} if ok else \
                hold("tighten rejected: " + m.rationale)
        return {"action": m.action, "new_stop": None, "rationale": m.rationale}
    except Exception as e:
        return hold(f"error: {type(e).__name__}")


if __name__ == "__main__":   # python -m trader.committee : one real committee run on live public SOL 4h data
    import sys
    import tempfile

    import ccxt

    from .store import Store

    sym = sys.argv[1] if len(sys.argv) > 1 else "SOL/USDT:USDT"
    ex = ccxt.binanceusdm()
    bars = ex.fetch_ohlcv(sym, "4h", limit=60)
    closes = [b[4] for b in bars]
    atr = sum(b[2] - b[3] for b in bars[-14:]) / 14
    ema = lambda n: sum(closes[-n:]) / n   # noqa: E731  (simple mean, demo only)
    price = closes[-1]
    side = "long" if price > ema(20) else "short"
    setup = {"symbol": sym, "side": side, "price": price, "atr": atr, "stop_dist": 2 * atr, "signal": "demo",
             "bar_time": bars[-1][0], "features": {"sma20": ema(20), "sma50": ema(50), "chg_6bars_pct": (price / closes[-7] - 1) * 100}}
    ctx = {"btc": {}, "derivs": {}, "news": [], "fear_greed": None, "equity": 18.0, "open_positions": []}
    st = Store(tempfile.mktemp(suffix=".db"))
    r = decide(setup, ctx, [], st)
    print(json.dumps(r, indent=1, default=str))
    print("cost_usd", r["cost"], "calls", len(st.all("llm_cost")))
