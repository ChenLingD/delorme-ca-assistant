"""Thin multi-provider chat wrapper. Every provider returns plain text; JSON parsing is shared."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass

from openai import OpenAI

log = logging.getLogger("delorme.llm")

# Per-run call log (served model, tokens, latency) — lets us audit silent model swaps or effort drops.
CALL_LOG: ContextVar[list | None] = ContextVar("CALL_LOG", default=None)


def _record(spec: "ModelSpec", resp, seconds: float, attempt: int) -> None:
    calls = CALL_LOG.get()
    if calls is None:
        return
    u = getattr(resp, "usage", None)
    rec = {"requested": spec.model, "served": getattr(resp, "model", None), "seconds": round(seconds, 1), "attempt": attempt + 1}
    if u is not None:
        rec["in_tokens"] = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", None)
        rec["out_tokens"] = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", None)
        det = getattr(u, "completion_tokens_details", None)
        rec["reasoning_tokens"] = getattr(det, "reasoning_tokens", None) if det else None
    rec["fingerprint"] = getattr(resp, "system_fingerprint", None)
    calls.append(rec)


@dataclass
class ModelSpec:
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


# provider -> (base_url, api-key env var)
_OPENAI_COMPAT = {
    "openai": (None, "OPENAI_API_KEY"),
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "kimi": ("https://api.moonshot.ai/v1", "MOONSHOT_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
}

DEFAULT_MODELS = {
    # bake-off line-up: frontier-tier but cost-efficient model from each vendor
    "openai": "gpt-6.1-terra",
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-3.8-flash",
    "deepseek": "deepseek-flash",  # stable alias; currently serves DeepSeek V4.1 Flash
    "kimi": "kimi-k3.1-pro",
}

_clients: dict[str, object] = {}


def parse_spec(s: str) -> ModelSpec:
    """'openai' or 'openai:gpt-5.5' -> ModelSpec."""
    provider, _, model = s.partition(":")
    return ModelSpec(provider, model or DEFAULT_MODELS[provider])


def _client(provider: str):
    if provider not in _clients:
        if provider == "anthropic":
            import anthropic

            _clients[provider] = anthropic.Anthropic(timeout=150, max_retries=0)
        else:
            base, env = _OPENAI_COMPAT[provider]
            # Kimi's reasoning model is slow on long prompts; give it more room
            timeout = 300 if provider == "kimi" else 150
            _clients[provider] = OpenAI(api_key=os.environ[env], base_url=base, timeout=timeout, max_retries=0)
    return _clients[provider]


OVERLOAD = {429, 500, 502, 503, 504}  # provider busy: worth waiting longer before retrying
# Opt-in (the demo sets MODEL_FALLBACK=1): after two busy/timeout failures, switch to an older sibling model.
# Batch/eval runs leave it off so results always come from the requested model; the call log records what served.
FALLBACK_MODEL = {"gemini": os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.7-flash")}


def _busy(e: Exception) -> bool:
    return getattr(e, "status_code", None) in OVERLOAD or "Timeout" in type(e).__name__


def chat(spec: ModelSpec, system: str, user: str, *, json_mode: bool = True, retries: int = 4) -> str:
    last_err: Exception | None = None
    model, busy_fails = spec.model, 0
    for attempt in range(retries):
        t0 = time.time()
        try:
            if spec.provider == "anthropic":
                resp = _client("anthropic").messages.create(
                    model=spec.model,
                    max_tokens=4000,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                _record(spec, resp, time.time() - t0, attempt)
                return "".join(b.text for b in resp.content if b.type == "text")
            kwargs = {}
            if json_mode and spec.provider in ("openai", "deepseek", "kimi", "gemini"):
                kwargs["response_format"] = {"type": "json_object"}
            resp = _client(spec.provider).chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                **kwargs,
            )
            log.info("%s ok %.1fs", spec.label, time.time() - t0)
            _record(spec, resp, time.time() - t0, attempt)
            return resp.choices[0].message.content or ""
        except Exception as e:  # network / rate limit: back off and retry
            log.warning("%s (%s) attempt %d failed after %.1fs: %r %s", spec.label, model, attempt + 1,
                        time.time() - t0, e, str(getattr(e, "body", "") or "")[:300])
            last_err = e
            busy = _busy(e)
            busy_fails += busy
            if busy_fails >= 2 and os.environ.get("MODEL_FALLBACK") == "1" and FALLBACK_MODEL.get(spec.provider):
                model = FALLBACK_MODEL[spec.provider]
            if attempt + 1 < retries:
                time.sleep((5, 15, 30)[min(attempt, 2)] if busy else 2 * (attempt + 1))
    raise RuntimeError(f"{spec.label} failed after {retries} attempts: {last_err}")


def parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def chat_json(spec: ModelSpec, system: str, user: str) -> dict:
    raw = chat(spec, system, user)
    try:
        return parse_json(raw)
    except Exception:
        # one repair attempt
        raw = chat(spec, system, user + "\n\n注意：只输出一个合法的 JSON 对象，不要任何其他文字。")
        return parse_json(raw)
