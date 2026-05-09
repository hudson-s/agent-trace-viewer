from __future__ import annotations

import argparse
import json
from pathlib import Path

from .parser import parse_file
from .renderers import (
    render_html,
    render_index_html,
    render_markdown,
    render_mermaid,
    render_mermaid_markdown,
    render_timeline_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent-trace",
        description="Parse agent chat JSON into tool-call timelines and diagrams.",
    )
    parser.add_argument("input", type=Path, help="Path to the chat JSON file.")
    parser.add_argument("--out", type=Path, help="Output directory. Writes all views when set.")
    parser.add_argument(
        "--format",
        choices=("markdown", "mermaid", "json", "html"),
        default="markdown",
        help="Format to print to stdout when --out is not set.",
    )
    args = parser.parse_args()

    trace = parse_file(args.input)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "timeline.json").write_text(render_timeline_json(trace), encoding="utf-8")
        (args.out / "trace.md").write_text(render_markdown(trace), encoding="utf-8")
        (args.out / "trace.mmd").write_text(render_mermaid(trace), encoding="utf-8")
        (args.out / "trace-diagram.md").write_text(render_mermaid_markdown(trace), encoding="utf-8")
        (args.out / "trace.html").write_text(render_html(trace), encoding="utf-8")
        index_root = args.out.parent
        (index_root / "index.html").write_text(render_index_html(_scan_records(index_root)), encoding="utf-8")
        print(f"Wrote trace views to {args.out}")
        print(f"Wrote index to {index_root / 'index.html'}")
        return 0

    renderers = {
        "markdown": render_markdown,
        "mermaid": render_mermaid,
        "json": render_timeline_json,
        "html": render_html,
    }
    print(renderers[args.format](trace), end="")
    return 0


def _scan_records(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for trace_html in sorted(root.glob("*/trace.html")):
        folder = trace_html.parent
        summary = _read_summary(folder / "timeline.json")
        records.append(
            {
                "title": folder.name,
                "href": f"{folder.name}/trace.html",
                "updated": _format_mtime(trace_html),
                "events": summary.get("events", 0),
                "tool_calls": summary.get("tool_calls", 0),
                "estimated_tokens": (
                    summary.get("estimated_tokens", {}).get("total", 0)
                    if isinstance(summary.get("estimated_tokens"), dict)
                    else 0
                ),
            }
        )
    return records


def _read_summary(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = data.get("summary") if isinstance(data, dict) else {}
    return summary if isinstance(summary, dict) else {}


def _format_mtime(path: Path) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    raise SystemExit(main())
