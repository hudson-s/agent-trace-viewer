from __future__ import annotations

import html
import json

from .model import Trace, TraceEvent
from .tokens import estimate_token_stats


def render_timeline_json(trace: Trace) -> str:
    token_stats = estimate_token_stats(trace)
    payload = {
        "source_format": trace.source_format,
        "summary": {
            "events": len(trace.events),
            "tool_calls": trace.tool_call_count,
            "tool_results": trace.tool_result_count,
            "estimated_tokens": token_stats,
        },
        "events": [_event_to_dict(event) for event in trace.events],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_markdown(trace: Trace) -> str:
    lines = [
        "# Agent Trace",
        "",
        f"- Source format: `{trace.source_format}`",
        f"- Parsed events: `{len(trace.events)}`",
        f"- Tool calls: `{trace.tool_call_count}`",
        f"- Tool results: `{trace.tool_result_count}`",
        "",
        "## Timeline",
        "",
    ]

    for event in trace.events:
        title = _event_title(event)
        lines.append(f"### {event.index}. {title}")
        if event.call_id:
            lines.append(f"- Call ID: `{event.call_id}`")
        if event.arguments not in (None, ""):
            lines.extend(["- Arguments:", "", _fence(event.arguments), ""])
        if event.result not in (None, "") and event.type == "tool_result":
            lines.extend(["- Result:", "", _fence(event.result), ""])
        elif event.content:
            lines.extend(["", _fence(event.content), ""])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_mermaid(trace: Trace) -> str:
    lines = [
        "sequenceDiagram",
        "  participant U as User",
        "  participant A as Agent",
        "  participant T as Tool",
        "",
    ]

    for event in trace.events:
        if event.type == "message" and event.role == "user":
            lines.append(f"  U->>A: {_mermaid_text(event.content)}")
        elif event.type == "message" and event.role == "assistant":
            lines.append(f"  A-->>U: {_mermaid_text(event.content)}")
        elif event.type == "tool_call":
            args = _short_json(event.arguments)
            lines.append(f"  A->>T: {_mermaid_text((event.name or 'tool') + '(' + args + ')')}")
        elif event.type == "tool_result":
            label = event.name or event.call_id or "tool result"
            lines.append(f"  T-->>A: {_mermaid_text(label + ': ' + _short_json(event.result or event.content))}")
        else:
            lines.append(f"  Note over A: {_mermaid_text(event.content or event.type)}")

    return "\n".join(lines).rstrip() + "\n"


def render_mermaid_markdown(trace: Trace) -> str:
    return "\n".join(
        [
            "# Agent Trace Diagram",
            "",
            f"- Source format: `{trace.source_format}`",
            f"- Parsed events: `{len(trace.events)}`",
            f"- Tool calls: `{trace.tool_call_count}`",
            f"- Tool results: `{trace.tool_result_count}`",
            "",
            "```mermaid",
            render_mermaid(trace).rstrip(),
            "```",
            "",
        ]
    )


def render_html(trace: Trace) -> str:
    timeline = []
    mermaid = render_mermaid(trace).rstrip()
    token_stats = estimate_token_stats(trace)
    event_counts = _counter_table(_count_by(trace.events, "type"))
    role_counts = _counter_table(_count_by(trace.events, "role"))
    token_event_rows = _counter_table(token_stats["by_event_type"], value_suffix=" tokens")
    token_role_rows = _counter_table(token_stats["by_role"], value_suffix=" tokens")
    for event in trace.events:
        detail_blocks = []
        if event.arguments not in (None, ""):
            detail_blocks.append(("Arguments", _pretty(event.arguments)))
        if event.result not in (None, "") and event.type == "tool_result":
            detail_blocks.append(("Result", _pretty(event.result)))
        elif event.content:
            detail_blocks.append(("Content", event.content))

        details = "".join(
            f"<section><h3>{html.escape(label)}</h3><pre>{html.escape(value)}</pre></section>"
            for label, value in detail_blocks
        )
        summary = _event_summary(event)
        timeline.append(
            "<details class='event'>"
            "<summary>"
            f"<span class='index'>{event.index}</span>"
            f"<span class='kind kind-{html.escape(event.type)}' title='{html.escape(_type_help(event.type))}'>{html.escape(event.type)}</span>"
            f"<span class='actor' title='{html.escape(_actor_help(event))}'>{html.escape(_event_actor(event))}</span>"
            f"<span class='summary-text'>{html.escape(summary)}</span>"
            "</summary>"
            f"<div class='details'>{details}</div>"
            "</details>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Trace</title>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{ startOnLoad: true, securityLevel: "loose", theme: "dark" }});
  </script>
  <style>
    :root {{
      --bg: #071019;
      --panel: #0d1824;
      --panel-2: #101f2e;
      --line: #234058;
      --line-bright: #2dd4bf;
      --text: #e6f1ff;
      --muted: #8aa4b8;
      --blue: #38bdf8;
      --green: #34d399;
      --amber: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: radial-gradient(circle at 18% 0%, rgba(56,189,248,.16), transparent 34%), radial-gradient(circle at 84% 10%, rgba(45,212,191,.12), transparent 30%), var(--bg); color: var(--text); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px; }}
    header {{ margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{ background: rgba(13,24,36,.86); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.02); }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .stat-box {{ background: linear-gradient(180deg, rgba(16,31,46,.96), rgba(13,24,36,.96)); border: 1px solid var(--line); border-radius: 8px; padding: 10px; box-shadow: 0 12px 30px rgba(0,0,0,.18); }}
    .stat-box h2 {{ margin: 0 0 8px; font-size: 14px; }}
    .stat-row {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 4px 0; border-top: 1px solid rgba(138,164,184,.16); font-size: 13px; }}
    .stat-row:first-of-type {{ border-top: 0; }}
    .stat-key {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: Consolas, monospace; }}
    .stat-value {{ color: var(--blue); font-variant-numeric: tabular-nums; }}
    .token-note {{ margin: 10px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .help {{ margin-top: 14px; background: rgba(13,24,36,.92); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    .help > summary {{ display: flex; grid-template-columns: none; gap: 8px; min-height: 42px; font-weight: 700; }}
    .help-icon {{ width: 22px; height: 22px; border-radius: 50%; display: inline-grid; place-items: center; background: linear-gradient(135deg, var(--blue), var(--line-bright)); color: #00131c; font-weight: 700; }}
    .help-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; border-top: 1px solid var(--line); padding: 14px; }}
    .help h2 {{ margin: 0 0 8px; font-size: 15px; }}
    .help p {{ margin: 0; line-height: 1.6; color: var(--muted); }}
    .help dl {{ margin: 0; display: grid; grid-template-columns: 96px 1fr; gap: 8px 10px; }}
    .help dt {{ font-weight: 700; font-family: Consolas, monospace; }}
    .help dd {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .diagram {{ margin: 14px 0; background: rgba(13,24,36,.94); border: 1px solid var(--line-bright); border-radius: 8px; overflow: hidden; box-shadow: 0 0 0 1px rgba(45,212,191,.08), 0 18px 50px rgba(0,0,0,.26); }}
    .diagram > summary {{ display: flex; grid-template-columns: none; gap: 8px; min-height: 42px; font-weight: 700; }}
    .diagram-toolbar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; border-top: 1px solid var(--line); padding: 10px 12px; background: rgba(7,16,25,.72); }}
    .diagram-toolbar button {{ border: 1px solid var(--line); background: var(--panel-2); color: var(--text); border-radius: 8px; padding: 7px 10px; cursor: pointer; }}
    .diagram-toolbar button:hover {{ border-color: var(--line-bright); color: var(--line-bright); }}
    .zoom-readout {{ color: var(--muted); font-variant-numeric: tabular-nums; margin-left: auto; }}
    .diagram-body {{ border-top: 1px solid var(--line); padding: 16px; overflow: auto; min-height: 420px; background: linear-gradient(rgba(45,212,191,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,191,.05) 1px, transparent 1px), #08131d; background-size: 28px 28px; }}
    .diagram-canvas {{ width: max-content; min-width: 100%; transform-origin: top left; transition: transform .12s ease; }}
    .mermaid {{ min-width: 920px; }}
    .trace-header {{ position: sticky; top: 0; z-index: 2; display: grid; grid-template-columns: 48px 110px 140px minmax(0, 1fr); gap: 10px; align-items: center; min-height: 36px; padding: 0 12px; margin-bottom: 8px; background: rgba(7,16,25,.96); border: 1px solid var(--line); border-radius: 8px; color: var(--muted); font-size: 13px; font-weight: 700; backdrop-filter: blur(10px); }}
    .event {{ background: rgba(13,24,36,.9); border: 1px solid var(--line); border-radius: 8px; margin: 6px 0; overflow: hidden; }}
    summary {{ display: grid; grid-template-columns: 48px 110px 140px minmax(0, 1fr); gap: 10px; align-items: center; min-height: 38px; padding: 0 12px; cursor: pointer; list-style: none; }}
    summary::-webkit-details-marker {{ display: none; }}
    summary:hover {{ background: rgba(56,189,248,.08); }}
    .index {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    .kind {{ width: fit-content; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; font-size: 12px; background: rgba(16,31,46,.9); }}
    .kind-tool_call {{ border-color: var(--blue); color: var(--blue); background: rgba(56,189,248,.12); }}
    .kind-tool_result {{ border-color: var(--green); color: var(--green); background: rgba(52,211,153,.12); }}
    .actor {{ font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .summary-text {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }}
    .details {{ border-top: 1px solid var(--line); padding: 12px; }}
    h3 {{ margin: 0 0 8px; font-size: 14px; }}
    section + section {{ margin-top: 12px; }}
    pre {{ max-height: 460px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; background: #08131d; color: #d8ecff; border: 1px solid var(--line); border-radius: 6px; padding: 12px; }}
    @media (max-width: 760px) {{
      .stats-grid {{ grid-template-columns: 1fr; }}
      .help-grid {{ grid-template-columns: 1fr; }}
      .help dl {{ grid-template-columns: 86px 1fr; }}
      .trace-header {{ grid-template-columns: 40px 92px minmax(0, 1fr); }}
      .trace-header span:nth-child(3) {{ display: none; }}
      summary {{ grid-template-columns: 40px 92px minmax(0, 1fr); }}
      .actor {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Agent Trace</h1>
      <div class="summary">
        <div class="pill">Format: {html.escape(trace.source_format)}</div>
        <div class="pill" title="解析器展开后的事件数。一个原始 message 可能被拆成 message 和 tool_call 两个事件。">Parsed events: {len(trace.events)}</div>
        <div class="pill">Tool calls: {trace.tool_call_count}</div>
        <div class="pill">Tool results: {trace.tool_result_count}</div>
        <div class="pill total-token" title="单位是 token：模型 tokenizer 切出来的分词单位，不是字数、字符数或费用。原 JSON 没有 usage 字段，所以这是估算值。">Total estimated tokens: {token_stats["total"]} tokens</div>
      </div>
      <div class="stats-grid">
        <section class="stat-box">
          <h2>事件数量</h2>
          {event_counts}
        </section>
        <section class="stat-box">
          <h2>角色数量</h2>
          {role_counts}
        </section>
        <section class="stat-box">
          <h2>事件类型 token</h2>
          {token_event_rows}
        </section>
        <section class="stat-box">
          <h2>角色 token</h2>
          {token_role_rows}
        </section>
      </div>
      <p class="token-note">Token 单位：模型分词单位，不等于汉字数、字符数或费用。这里用 {html.escape(token_stats["method"])} 估算 transcript 文本足迹；原始 JSON 没有 usage 字段，所以不能还原真实计费 token。多轮 agent 实际消耗通常会高于这里的一次性展开统计。</p>
      <details class="help">
        <summary><span class="help-icon">?</span><span>怎么看这张 trace</span></summary>
        <div class="help-grid">
          <section>
            <h2>一条记录代表什么</h2>
            <p>页面里每一行都是 agent 执行过程中的一个事件。先看左边的类型，再看角色/工具名，最后看右侧摘要。点开一行可以看到完整内容。</p>
          </section>
          <section>
            <h2>事件类型</h2>
            <dl>
              <dt>message</dt><dd>普通对话消息，比如用户提问或 assistant 回复。</dd>
              <dt>tool_call</dt><dd>assistant 决定调用某个工具，常见例子是执行命令、搜索、读文件、写记忆。</dd>
              <dt>tool_result</dt><dd>工具执行后的返回结果，通常和前面的 tool_call 配对看。</dd>
              <dt>unknown</dt><dd>解析器暂时不认识的原始事件，通常需要补适配规则。</dd>
            </dl>
          </section>
          <section>
            <h2>常见角色</h2>
            <dl>
              <dt>user</dt><dd>用户输入的内容，也就是任务来源。</dd>
              <dt>assistant</dt><dd>agent 或模型的回复，有时会先请求工具而不是直接回答。</dd>
              <dt>tool</dt><dd>工具返回的消息，例如 terminal 的执行结果。</dd>
              <dt>工具名</dt><dd>当这一列显示 terminal、memory、read_file 等名字时，表示这行和具体工具有关。</dd>
            </dl>
          </section>
          <section>
            <h2>阅读顺序</h2>
            <p>推荐按时间从上往下看：user 提问 -> assistant 选择工具 -> tool_result 返回证据 -> assistant 总结。这样就能看懂 agent 每一步为什么这么做。</p>
          </section>
          <section>
            <h2>Token 是什么</h2>
            <p>Token 是模型处理文本时的最小分词单位。一个中文词、一个英文单词、标点或 JSON 片段都可能被切成不同数量的 token。本页显示的是估算值。</p>
          </section>
        </div>
      </details>
      <details class="diagram" open>
        <summary><span class="help-icon">?</span><span>流程图</span></summary>
        <div class="diagram-toolbar">
          <button type="button" data-zoom="out">缩小</button>
          <button type="button" data-zoom="in">放大</button>
          <button type="button" data-zoom="reset">100%</button>
          <button type="button" data-zoom="fit">适配宽度</button>
          <button type="button" id="openDiagram">弹出查看整图</button>
          <span class="zoom-readout" id="zoomReadout">100%</span>
        </div>
        <div class="diagram-body">
          <div class="diagram-canvas" id="diagramCanvas">
            <pre class="mermaid">{html.escape(mermaid)}</pre>
          </div>
        </div>
      </details>
    </header>
    <div class="trace-header" aria-hidden="true">
      <span>序号</span>
      <span>事件类型</span>
      <span>角色/工具</span>
      <span>摘要</span>
    </div>
    {''.join(timeline)}
  </main>
  <script>
    const canvas = document.getElementById("diagramCanvas");
    const body = document.querySelector(".diagram-body");
    const readout = document.getElementById("zoomReadout");
    let zoom = 1;

    function applyZoom() {{
      canvas.style.transform = `scale(${{zoom}})`;
      const rect = canvas.getBoundingClientRect();
      canvas.style.width = `${{rect.width / zoom}}px`;
      canvas.style.minHeight = `${{rect.height / zoom}}px`;
      readout.textContent = `${{Math.round(zoom * 100)}}%`;
    }}

    function fitDiagram() {{
      const svg = canvas.querySelector("svg");
      if (!svg) return;
      const svgWidth = svg.getBBox ? svg.getBBox().width : svg.clientWidth;
      if (!svgWidth) return;
      zoom = Math.max(0.35, Math.min(2.5, (body.clientWidth - 24) / svgWidth));
      applyZoom();
    }}

    document.querySelectorAll("[data-zoom]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const action = button.dataset.zoom;
        if (action === "in") zoom = Math.min(3, zoom + 0.2);
        if (action === "out") zoom = Math.max(0.3, zoom - 0.2);
        if (action === "reset") zoom = 1;
        if (action === "fit") return fitDiagram();
        applyZoom();
      }});
    }});

    document.getElementById("openDiagram").addEventListener("click", () => {{
      const svg = canvas.querySelector("svg");
      if (!svg) {{
        alert("流程图还没有渲染完成，请稍后再试。");
        return;
      }}
      const clone = svg.cloneNode(true);
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      clone.style.background = "#08131d";
      const source = new XMLSerializer().serializeToString(clone);
      const page = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Agent Trace Diagram</title>
  <style>
    html, body {{
      margin: 0;
      min-height: 100%;
      background: #071019;
      color: #e6f1ff;
      font-family: Arial, sans-serif;
    }}
    body {{
      background:
        radial-gradient(circle at 18% 0%, rgba(56,189,248,.18), transparent 34%),
        radial-gradient(circle at 84% 10%, rgba(45,212,191,.14), transparent 30%),
        #071019;
    }}
    .bar {{
      position: sticky;
      top: 0;
      z-index: 1;
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 10px 14px;
      background: rgba(7,16,25,.92);
      border-bottom: 1px solid #234058;
      backdrop-filter: blur(10px);
    }}
    .bar strong {{ color: #38bdf8; }}
    .hint {{ color: #8aa4b8; font-size: 13px; }}
    .stage {{
      padding: 24px;
      overflow: auto;
      min-height: calc(100vh - 46px);
      background:
        linear-gradient(rgba(45,212,191,.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(45,212,191,.05) 1px, transparent 1px);
      background-size: 28px 28px;
    }}
    svg {{
      display: block;
      min-width: 1200px;
      background: #08131d;
      border: 1px solid #2dd4bf;
      border-radius: 8px;
      box-shadow: 0 18px 60px rgba(0,0,0,.38);
    }}
  </style>
</head>
<body>
  <div class="bar"><strong>Agent Trace Diagram</strong><span class="hint">使用浏览器缩放、滚轮和滚动条查看整图</span></div>
  <div class="stage">${{source}}</div>
</body>
</html>`;
      const blob = new Blob([page], {{ type: "text/html;charset=utf-8" }});
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }});

    window.addEventListener("load", () => setTimeout(applyZoom, 300));
  </script>
</body>
</html>
"""


def render_records_js(records: list[dict[str, object]]) -> str:
    return "window.AGENT_TRACE_RECORDS = " + json.dumps(records, ensure_ascii=False, indent=2) + ";\n"


def render_index_html(records: list[dict[str, object]] | None = None) -> str:
    initial_records = json.dumps(records or [], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Trace Viewer</title>
  <style>
    :root {{
      --bg: #071019;
      --panel: #0d1824;
      --panel-2: #101f2e;
      --line: #234058;
      --line-bright: #2dd4bf;
      --text: #e6f1ff;
      --muted: #8aa4b8;
      --blue: #38bdf8;
      --green: #34d399;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: radial-gradient(circle at 20% 0%, rgba(56,189,248,.18), transparent 34%), radial-gradient(circle at 82% 12%, rgba(45,212,191,.13), transparent 30%), var(--bg); color: var(--text); }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 30px 18px; }}
    .hero {{ padding: 18px 0 8px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    .lead {{ margin: 0 0 22px; color: var(--muted); line-height: 1.6; }}
    .panel {{ background: linear-gradient(180deg, rgba(16,31,46,.96), rgba(13,24,36,.96)); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin: 14px 0; box-shadow: 0 18px 50px rgba(0,0,0,.24); }}
    .panel h2 {{ margin: 0 0 12px; font-size: 18px; }}
    input[type="file"] {{ display: block; width: 100%; max-width: 560px; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: #08131d; color: var(--text); }}
    input[type="file"]::file-selector-button {{ border: 1px solid var(--line-bright); border-radius: 8px; background: rgba(45,212,191,.12); color: var(--text); padding: 7px 10px; margin-right: 10px; cursor: pointer; }}
    .hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .preview {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: rgba(8,19,29,.86); }}
    .metric b {{ display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    .metric span {{ font-size: 18px; font-weight: 700; overflow-wrap: anywhere; }}
    .records {{ display: grid; gap: 10px; }}
    .record {{ background: rgba(13,24,36,.92); border: 1px solid var(--line); border-radius: 8px; padding: 14px; transition: border-color .15s ease, transform .15s ease; }}
    .record:hover {{ border-color: var(--line-bright); transform: translateY(-1px); }}
    .record a {{ color: var(--blue); text-decoration: none; }}
    .record a:hover {{ text-decoration: underline; }}
    .record h2 {{ margin: 0 0 10px; font-size: 18px; }}
    .record-meta {{ display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }}
    .record-meta span {{ border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; background: rgba(8,19,29,.8); }}
    .empty {{ color: var(--muted); }}
    .path-box {{ margin: 10px 0; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: rgba(8,19,29,.86); color: var(--muted); overflow-wrap: anywhere; }}
    .path-box strong {{ color: var(--text); }}
    code {{ background: #08131d; border: 1px solid var(--line); border-radius: 6px; padding: 2px 5px; color: var(--green); }}
    @media (max-width: 760px) {{
      .preview {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Agent Trace Viewer</h1>
      <p class="lead">选择本地 JSON 做快速预览，或进入已经生成好的 trace。适合学习 agent 每一步如何对话、调用工具、读取结果。</p>
    </section>

    <section class="panel">
      <h2>选择本地 JSON</h2>
      <input id="jsonFile" type="file" accept=".json,application/json">
      <p class="hint">浏览器安全限制下，静态 HTML 只能读取你主动选择的文件并做预览，不能自动写入生成结果。完整 trace 请继续用 CLI 生成；生成后刷新本页查看最新记录。</p>
      <div id="preview" class="preview" hidden></div>
      <p id="commandHint" class="hint"></p>
    </section>

    <section class="panel">
      <h2>已生成记录</h2>
      <div class="path-box">
        <div><strong>默认记录目录：</strong><code>./out</code></div>
        <div><strong>当前记录来源：</strong><span id="recordSource">等待加载</span></div>
      </div>
      <p class="hint">CLI 生成 trace 后会更新 <code>records.js</code>。如果页面已经打开，使用浏览器刷新即可看到最新记录。</p>
      <div id="records" class="records"></div>
    </section>
  </main>
  <script src="records.js"></script>
  <script>
    const initialRecords = window.AGENT_TRACE_RECORDS || {initial_records};
    const input = document.getElementById("jsonFile");
    const preview = document.getElementById("preview");
    const commandHint = document.getElementById("commandHint");
    const recordsEl = document.getElementById("records");
    const recordSource = document.getElementById("recordSource");

    function renderRecords(records, sourceLabel = "records.js -> ./out") {{
      recordSource.textContent = sourceLabel;
      if (!records.length) {{
        recordsEl.innerHTML = `<p class="empty">还没有生成过 trace。先用 CLI 生成一个记录，然后刷新本页。</p>`;
        return;
      }}
      recordsEl.innerHTML = records.map((record) => {{
        const title = escapeHtml(record.title || "Untitled trace");
        const href = escapeHtml(record.href || "#");
        const updated = escapeHtml(record.updated || "");
        const events = escapeHtml(String(record.events ?? 0));
        const toolCalls = escapeHtml(String(record.tool_calls ?? 0));
        const tokens = escapeHtml(String(record.estimated_tokens ?? 0));
        return `<article class="record">
          <a href="${{href}}"><h2>${{title}}</h2></a>
          <div class="record-meta">
            <span>Parsed events: ${{events}}</span>
            <span>Tool calls: ${{toolCalls}}</span>
            <span>Estimated tokens: ${{tokens}}</span>
            <span>Updated: ${{updated}}</span>
          </div>
        </article>`;
      }}).join("");
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function countToolCalls(messages) {{
      return messages.reduce((sum, message) => {{
        const calls = Array.isArray(message && message.tool_calls) ? message.tool_calls.length : 0;
        return sum + calls;
      }}, 0);
    }}

    function metric(label, value) {{
      return `<div class="metric"><b>${{label}}</b><span>${{value ?? ""}}</span></div>`;
    }}

    input.addEventListener("change", async () => {{
      const file = input.files && input.files[0];
      if (!file) return;
      try {{
        const text = await file.text();
        const data = JSON.parse(text);
        const messages = Array.isArray(data) ? data : Array.isArray(data.messages) ? data.messages : [];
        const sessionId = data.session_id || file.name.replace(/\\.json$/i, "");
        preview.innerHTML = [
          metric("文件", file.name),
          metric("Session", sessionId),
          metric("Model", data.model || "unknown"),
          metric("Platform", data.platform || "unknown"),
          metric("Messages", messages.length),
          metric("Tool calls", countToolCalls(messages)),
          metric("Size", `${{Math.round(file.size / 1024)}} KB`),
          metric("Source", Array.isArray(data) ? "message_list" : "json_object")
        ].join("");
        preview.hidden = false;
        commandHint.innerHTML = `生成完整视图：<code>agent-trace "${{file.name}}" --out out/${{sessionId}}</code>`;
      }} catch (error) {{
        preview.innerHTML = metric("解析失败", error.message);
        preview.hidden = false;
        commandHint.textContent = "";
      }}
    }});

    renderRecords(initialRecords, initialRecords.length ? "records.js -> ./out" : "records.js -> ./out（暂无记录）");
  </script>
</body>
</html>
"""


def _event_to_dict(event: TraceEvent) -> dict[str, object]:
    return {
        "index": event.index,
        "type": event.type,
        "role": event.role,
        "name": event.name,
        "call_id": event.call_id,
        "content": event.content,
        "arguments": event.arguments,
        "result": event.result,
    }


def _count_by(events: list[TraceEvent], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        key = str(getattr(event, attr))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _counter_table(counts: dict[str, int], value_suffix: str = "") -> str:
    if not counts:
        return "<div class='stat-row'><span class='stat-key'>none</span><span class='stat-value'>0</span></div>"
    rows = []
    for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        rows.append(
            "<div class='stat-row'>"
            f"<span class='stat-key'>{html.escape(str(key))}</span>"
            f"<span class='stat-value'>{value}{html.escape(value_suffix)}</span>"
            "</div>"
        )
    return "".join(rows)


def _event_title(event: TraceEvent) -> str:
    if event.type == "tool_call":
        return f"tool_call: {event.name}"
    if event.type == "tool_result":
        return f"tool_result: {event.name or event.call_id or 'unknown'}"
    return f"{event.type}: {event.role}"


def _event_actor(event: TraceEvent) -> str:
    if event.type in ("tool_call", "tool_result"):
        return event.name or event.call_id or "unknown_tool"
    return event.role


def _type_help(event_type: str) -> str:
    help_text = {
        "message": "普通对话消息：用户输入或 assistant 回复。",
        "tool_call": "工具调用请求：assistant 准备调用一个外部工具。",
        "tool_result": "工具返回结果：外部工具执行后返回给 assistant 的证据。",
        "unknown": "未知事件：当前解析器还没有识别这种结构。",
    }
    return help_text.get(event_type, "事件类型。")


def _actor_help(event: TraceEvent) -> str:
    if event.type in ("tool_call", "tool_result"):
        return "工具名或工具调用 ID，用来判断是哪一个工具参与了这一步。"
    role_help = {
        "user": "用户，也就是提出需求的人。",
        "assistant": "assistant/agent，也就是根据上下文做决策和回复的一方。",
        "tool": "工具消息，通常是命令、搜索、文件读取等外部动作的返回。",
        "system": "系统提示，定义 assistant 的身份、规则或边界。",
    }
    return role_help.get(event.role, "消息角色。")


def _event_summary(event: TraceEvent) -> str:
    if event.type == "tool_call":
        return _short_json(event.arguments, limit=180)
    if event.type == "tool_result":
        return _short_json(event.result if event.result not in (None, "") else event.content, limit=180)
    return _one_line(event.content, limit=180)


def _fence(value: object) -> str:
    if isinstance(value, str):
        return f"```text\n{value}\n```"
    return f"```json\n{_pretty(value)}\n```"


def _pretty(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _short_json(value: object, limit: int = 100) -> str:
    text = _pretty(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1] + "..."
    return text


def _one_line(value: str, limit: int = 100) -> str:
    text = " ".join(value.split())
    if len(text) > limit:
        return text[: limit - 1] + "..."
    return text


def _mermaid_text(value: str) -> str:
    return value.replace("\n", " ").replace(";", ",")[:120]
