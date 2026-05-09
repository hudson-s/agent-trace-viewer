from __future__ import annotations

from collections import Counter
import json
from typing import Any

from .model import Trace, TraceEvent


def estimate_token_stats(trace: Trace) -> dict[str, Any]:
    counter = _get_counter()
    event_type_tokens: Counter[str] = Counter()
    role_tokens: Counter[str] = Counter()
    total = 0

    for event in trace.events:
        tokens = counter(_event_token_text(event))
        event_type_tokens[event.type] += tokens
        role_tokens[event.role] += tokens
        total += tokens

    return {
        "method": "tiktoken:o200k_base" if _has_tiktoken() else "rough:chars/4",
        "unit": "tokens",
        "is_estimate": True,
        "note": "Estimated transcript footprint only; source JSON has no usage fields.",
        "total": total,
        "by_event_type": dict(event_type_tokens),
        "by_role": dict(role_tokens),
    }


def _event_token_text(event: TraceEvent) -> str:
    if event.type == "tool_call":
        return "\n".join([event.name or "", _jsonish(event.arguments)])
    if event.type == "tool_result":
        return "\n".join([event.name or event.call_id or "", _jsonish(event.result), event.content])
    return event.content


def _jsonish(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _has_tiktoken() -> bool:
    try:
        import tiktoken  # noqa: F401
    except Exception:
        return False
    return True


def _get_counter():
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("o200k_base")
        return lambda text: len(encoding.encode(text or ""))
    except Exception:
        return lambda text: max(1, round(len(text or "") / 4)) if text else 0
