"""One OpenAI-compatible client for GLM, Kimi, OpenAI and Claude. Any failure means 'hold'."""
import json
import os
import time
from pathlib import Path
from typing import Literal

from openai import OpenAI
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


class LLM:
    def __init__(self):
        self.model = os.environ["LLM_MODEL"]
        self.client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"],
                             timeout=60, max_retries=2)
        self.schema_mode = os.getenv("LLM_SCHEMA", "json_schema")   # json_schema | json_object
        self.price_in = float(os.getenv("LLM_PRICE_IN", "0"))       # USD per 1M tokens
        self.price_out = float(os.getenv("LLM_PRICE_OUT", "0"))
        self.debug = False   # --dry prints the full provider error to stdout (never to the store or Telegram)

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
