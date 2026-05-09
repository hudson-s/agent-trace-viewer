from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import Trace, TraceEvent


def parse_file(path: Path) -> Trace:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return parse_data(data)


def parse_data(data: Any) -> Trace:
    messages = _extract_messages(data)
    events: list[TraceEvent] = []

    for message in messages:
        if not isinstance(message, dict):
            events.append(
                TraceEvent(
                    index=len(events) + 1,
                    type="unknown",
                    role="unknown",
                    content=_compact(message),
                    raw={"value": message},
                )
            )
            continue

        role = str(message.get("role") or message.get("type") or "unknown")
        content = _extract_content(message)

        if role == "tool" or "tool_call_id" in message:
            events.append(
                TraceEvent(
                    index=len(events) + 1,
                    type="tool_result",
                    role=role,
                    content=content,
                    name=_optional_str(message.get("name")),
                    call_id=_optional_str(message.get("tool_call_id") or message.get("id")),
                    result=_parse_jsonish(message.get("content", content)),
                    raw=message,
                )
            )
            continue

        if content:
            events.append(
                TraceEvent(
                    index=len(events) + 1,
                    type="message",
                    role=role,
                    content=content,
                    name=_optional_str(message.get("name")),
                    raw=message,
                )
            )

        for tool_call in _extract_tool_calls(message):
            events.append(_tool_call_event(len(events) + 1, role, tool_call))

    return Trace(source_format=_guess_format(data), events=events)


def _extract_messages(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return [data]

    for key in ("messages", "conversation", "items", "events"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    choices = data.get("choices")
    if isinstance(choices, list):
        messages = []
        for choice in choices:
            if isinstance(choice, dict) and isinstance(choice.get("message"), dict):
                messages.append(choice["message"])
        if messages:
            return messages

    return [data]


def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        return [call for call in tool_calls if isinstance(call, dict)]

    # Some traces store a single tool call directly on the message.
    if message.get("function_call") or message.get("tool_call"):
        call = message.get("function_call") or message.get("tool_call")
        if isinstance(call, dict):
            return [call]

    return []


def _tool_call_event(index: int, role: str, tool_call: dict[str, Any]) -> TraceEvent:
    function = tool_call.get("function")
    if isinstance(function, dict):
        name = _optional_str(function.get("name"))
        arguments = _parse_jsonish(function.get("arguments"))
    else:
        name = _optional_str(tool_call.get("name") or tool_call.get("tool_name"))
        arguments = _parse_jsonish(tool_call.get("arguments") or tool_call.get("input"))

    return TraceEvent(
        index=index,
        type="tool_call",
        role=role,
        content="",
        name=name or "unknown_tool",
        call_id=_optional_str(tool_call.get("id") or tool_call.get("tool_call_id")),
        arguments=arguments,
        raw=tool_call,
    )


def _extract_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
                else:
                    parts.append(_compact(item))
            else:
                parts.append(_compact(item))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return _compact(content)


def _parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _compact(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


def _guess_format(data: Any) -> str:
    if isinstance(data, dict):
        if "choices" in data:
            return "openai_response"
        if "messages" in data:
            return "chat_messages"
    if isinstance(data, list):
        return "message_list"
    return "unknown"
