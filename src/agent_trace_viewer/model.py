from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EventType = Literal["message", "tool_call", "tool_result", "unknown"]


@dataclass(slots=True)
class TraceEvent:
    index: int
    type: EventType
    role: str
    content: str = ""
    name: str | None = None
    call_id: str | None = None
    arguments: Any = None
    result: Any = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trace:
    source_format: str
    events: list[TraceEvent]

    @property
    def tool_call_count(self) -> int:
        return sum(1 for event in self.events if event.type == "tool_call")

    @property
    def tool_result_count(self) -> int:
        return sum(1 for event in self.events if event.type == "tool_result")
