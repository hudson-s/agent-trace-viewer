from pathlib import Path

from agent_trace_viewer.cli import _scan_records
from agent_trace_viewer.parser import parse_file
from agent_trace_viewer.renderers import render_html, render_mermaid, render_mermaid_markdown, render_records_js


def test_parse_openai_chat_fixture() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))

    assert trace.source_format == "chat_messages"
    assert len(trace.events) == 5
    assert trace.tool_call_count == 1
    assert trace.tool_result_count == 1
    assert trace.events[2].name == "web_search"
    assert trace.events[2].arguments == {"query": "agent tracing tools"}
    assert trace.events[3].result == {"results": ["Phoenix", "Langfuse", "LangSmith"]}


def test_render_mermaid_contains_tool_call() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    mermaid = render_mermaid(trace)

    assert "sequenceDiagram" in mermaid
    assert "web_search" in mermaid


def test_render_mermaid_markdown_wraps_diagram() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    markdown = render_mermaid_markdown(trace)

    assert "```mermaid" in markdown
    assert "sequenceDiagram" in markdown


def test_render_html_uses_collapsible_rows() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    page = render_html(trace)

    assert "<details class='event'>" in page
    assert "<summary>" in page


def test_render_html_includes_beginner_help() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    page = render_html(trace)

    assert "怎么看这张 trace" in page
    assert "事件类型" in page
    assert "常见角色" in page
    assert "assistant 决定调用某个工具" in page


def test_render_html_embeds_mermaid_diagram() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    page = render_html(trace)

    assert "mermaid.esm.min.mjs" in page
    assert '<pre class="mermaid">' in page
    assert "sequenceDiagram" in page
    assert 'data-zoom="in"' in page
    assert 'data-zoom="fit"' in page
    assert 'id="openDiagram"' in page
    assert "Agent Trace Diagram" in page
    assert "text/html;charset=utf-8" in page


def test_render_html_includes_trace_column_header() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    page = render_html(trace)

    assert 'class="trace-header"' in page
    assert "事件类型" in page
    assert "角色/工具" in page


def test_render_html_includes_token_stats() -> None:
    trace = parse_file(Path("tests/fixtures/openai-chat.json"))
    page = render_html(trace)

    assert "Total estimated tokens" in page
    assert "Token 单位" in page
    assert "事件类型 token" in page
    assert "角色 token" in page


def test_static_index_html_has_file_picker_and_records() -> None:
    page = Path("index.html").read_text(encoding="utf-8")

    assert 'type="file"' in page
    assert 'src="records.js"' in page
    assert "已生成记录" in page
    assert "默认记录目录" in page
    assert "当前记录来源" in page
    assert "选择 out 目录刷新记录" not in page
    assert "重新载入入口页" not in page
    assert "Estimated tokens" in page
    assert "--bg: #071019" in page


def test_render_records_js_sets_global_records() -> None:
    script = render_records_js([{"title": "session_1", "href": "out/session_1/trace.html"}])

    assert "window.AGENT_TRACE_RECORDS" in script
    assert "out/session_1/trace.html" in script


def test_scan_records_links_from_project_root(tmp_path: Path) -> None:
    trace_dir = tmp_path / "out" / "session_1"
    trace_dir.mkdir(parents=True)
    (trace_dir / "trace.html").write_text("<html></html>", encoding="utf-8")
    (trace_dir / "timeline.json").write_text(
        '{"summary":{"events":5,"tool_calls":2,"estimated_tokens":{"total":42}}}',
        encoding="utf-8",
    )

    records = _scan_records(tmp_path / "out", tmp_path)

    assert records[0]["href"] == "out/session_1/trace.html"
    assert records[0]["events"] == 5
    assert records[0]["estimated_tokens"] == 42
