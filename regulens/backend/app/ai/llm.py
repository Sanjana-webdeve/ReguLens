"""Gemini wrapper. Every caller must handle LLMUnavailable so the app degrades gracefully (NFR-09)."""
import json
import logging
import re
import time

from app.core import metrics
from app.core.config import settings

log = logging.getLogger("regulens.llm")
_client = None


class LLMUnavailable(Exception):
    pass


def is_available() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _get_client():
    global _client
    if not is_available():
        raise LLMUnavailable("No GEMINI_API_KEY configured.")
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate(prompt: str, system: str | None = None, json_mode: bool = False, temperature: float = 0.1) -> str:
    from google.genai import types

    client = _get_client()
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    last = None
    for attempt in range(3):
        t0 = time.perf_counter()
        try:
            resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt, config=cfg)
            metrics.observe("llm_latency", (time.perf_counter() - t0) * 1000)
            usage = getattr(resp, "usage_metadata", None)
            if usage and getattr(usage, "total_token_count", None):
                metrics.incr("llm_tokens", usage.total_token_count)
            metrics.incr("llm_calls")
            return resp.text or ""
        except Exception as e:  # network, quota, safety...
            last = e
            metrics.incr("llm_failures")
            log.warning("LLM call failed (attempt %s): %s", attempt + 1, e)
            time.sleep(1.5 * (attempt + 1))
    raise LLMUnavailable(str(last))


def generate_json(prompt: str, system: str | None = None):
    raw = generate(prompt, system=system, json_mode=True)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMUnavailable(f"LLM returned invalid JSON: {e}")
