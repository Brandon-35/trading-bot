"""One OpenAI-compatible client for GLM, Kimi, OpenAI and Claude. Any failure means 'hold'."""
import json
import os
import time
from pathlib import Path
from typing import Literal

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI
from pydantic import BaseModel, Field, ValidationError

PROMPT = (Path(__file__).parent.parent / "prompts" / "system.md").read_text()


class Decision(BaseModel):
    symbol: str
    action: Literal["long", "short", "close", "hold"]
    stop_loss: float | None = None
    take_profit: float | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class Reply(BaseModel):
    decisions: list[Decision]


def _schema() -> dict:
    # strict json_schema needs every property required and no extra keys
    s = Reply.model_json_schema()
    d = s["$defs"]["Decision"]
    d["required"] = list(d["properties"])
    d["additionalProperties"] = False
    for p in d["properties"].values():
        p.pop("default", None)
        p.pop("minimum", None)   # some strict-schema providers reject numeric bounds; pydantic still checks them
        p.pop("maximum", None)
    s["additionalProperties"] = False
    return {"type": "json_schema", "json_schema": {"name": "reply", "strict": True, "schema": s}}


# key env, base_url, model, schema mode, $ per 1M tokens in/out; first key present wins (cheapest first)
PROVIDERS = [
    ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-6-luna", "json_schema", 0.10, 0.50),
    ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/", "claude-haiku-5-5", "json_schema", 0.10, 0.50),
    ("ZAI_API_KEY", "https://api.z.ai/api/paas/v4", "glm-5.3-flash", "json_object", 0.15, 0.50),
    ("MOONSHOT_API_KEY", "https://api.moonshot.ai/v1", "kimi-k3.1-pro", "json_object", 2.00, 10.00),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-5.5"),
     "json_schema", float(os.getenv("OPENROUTER_PRICE_IN", "0.10")), float(os.getenv("OPENROUTER_PRICE_OUT", "0.50"))),
]


def pick() -> dict:
    """Explicit LLM_* env wins; otherwise the first provider whose API key is set."""
    if os.getenv("LLM_API_KEY"):
        return {"key": os.environ["LLM_API_KEY"], "url": os.environ["LLM_BASE_URL"], "model": os.environ["LLM_MODEL"],
                "schema": os.getenv("LLM_SCHEMA", "json_schema"), "pin": float(os.getenv("LLM_PRICE_IN", "0")),
                "pout": float(os.getenv("LLM_PRICE_OUT", "0"))}
    for env, url, model, schema, pin, pout in PROVIDERS:
        if os.getenv(env):
            return {"key": os.environ[env], "url": url, "model": model, "schema": schema, "pin": pin, "pout": pout}
    raise SystemExit("no LLM key: set one of " + ", ".join(p[0] for p in PROVIDERS))


class LLM:
    def __init__(self):
        c = pick()
        self.model = c["model"]
        self.client = OpenAI(base_url=c["url"], api_key=c["key"], timeout=60, max_retries=2)
        self.schema_mode = c["schema"]   # json_schema | json_object
        self.price_in, self.price_out = c["pin"], c["pout"]   # USD per 1M tokens
        self.debug = False   # --dry prints the full provider error to stdout (never to the store or Discord)

    def decide(self, snapshot: dict) -> tuple[list[Decision], dict]:
        """Return (decisions, call metadata). Decisions are [] on any error."""
        fmt = _schema() if self.schema_mode == "json_schema" else {"type": "json_object"}
        meta: dict = {"model": self.model, "schema": self.schema_mode}
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(
                model=self.model, temperature=0, response_format=fmt,
                messages=[{"role": "system", "content": PROMPT},
                          {"role": "user", "content": json.dumps(snapshot, separators=(",", ":"))}])
            text = r.choices[0].message.content or ""
            u = r.usage
            meta.update(ms=int((time.time() - t0) * 1000), tokens_in=u.prompt_tokens if u else 0,
                        tokens_out=u.completion_tokens if u else 0, raw=text[:4000])
            meta["cost"] = (meta["tokens_in"] * self.price_in + meta["tokens_out"] * self.price_out) / 1e6
            return Reply.model_validate_json(_strip_fence(text)).decisions, meta
        except (ValidationError, ValueError) as e:
            meta["error"] = f"invalid reply: {e}"[:500]
        except Exception as e:   # network, auth, rate limit: hold this cycle
            # provider messages can echo part of the key, so keep only the class and HTTP status
            meta["error"] = f"{type(e).__name__} {getattr(e, 'status_code', '')}".strip()
            if self.debug:
                print(f"provider error detail: {e}")
        meta.setdefault("ms", int((time.time() - t0) * 1000))
        return [], meta


# USD per 1M tokens (in, out): fallback when OpenRouter does not return usage.cost
PRICES = {"deepseek/deepseek-v3.2": (0.26, 0.38), "qwen/qwen3-235b-a22b-2507": (0.14, 0.80),
          "google/gemini-2.5-flash-lite": (0.10, 0.40)}


def _client() -> OpenAI:
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                  timeout=60, max_retries=0)


def chat(model: str, messages: list[dict], max_tokens=600, temperature=0.3, json_mode=True) -> tuple[str, float]:
    """One OpenRouter call -> (content, cost_usd). One retry on 5xx/timeout; raises on failure."""
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    for attempt in (0, 1):
        try:
            r = _client().chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
                extra_body={"usage": {"include": True}}, **kw)
            break
        except (APITimeoutError, APIConnectionError, InternalServerError):
            if attempt:
                raise
    u = r.usage
    cost = getattr(u, "cost", None) if u else None
    if cost is None and u:
        pin, pout = PRICES.get(model, (0.0, 0.0))
        cost = (u.prompt_tokens * pin + u.completion_tokens * pout) / 1e6
    return r.choices[0].message.content or "", float(cost or 0.0)


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return t


if __name__ == "__main__":   # python -m trader.llm --dry : one real call on a tiny snapshot
    demo = {"time_utc": "dry-run", "equity": 100, "open_positions": [], "symbols": {
        "BTC/USDT:USDT": {"price": 60000, "atr_1h": 600, "rsi_1h": 55, "ema20_1h": 59800, "ema50_1h": 59000,
                          "funding": 0.0001, "candles_1h": [[59500, 60100, 59400, 60000, 1200]]}}}
    llm = LLM()
    llm.debug = True
    ds, m = llm.decide(demo)
    print(json.dumps({"decisions": [d.model_dump() for d in ds], **{k: v for k, v in m.items() if k != "raw"}}, indent=1))
