"""Save trajectory JSON and a simple HTML replay page."""

from __future__ import annotations

import html
import json
from pathlib import Path


def write_trajectory_files(
    data: dict,
    out_dir: Path,
    *,
    home_href: str = "/",
) -> tuple[Path, Path]:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "trajectory.json"
    html_path = out_dir / "trajectory.html"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(_render_html(data, home_href=home_href), encoding="utf-8")
    return json_path, html_path


def _render_html(data: dict, *, home_href: str = "/") -> str:
    messages = data.get("messages") or []
    i2p = data.get("issue2patch") or {}
    todos = i2p.get("final_todos") or []
    info = data.get("info") or {}

    todo_rows = "".join(
        f"<li><code>{html.escape(t.get('status', ''))}</code> {html.escape(t.get('text', ''))}</li>"
        for t in todos
    )
    msg_blocks = []
    for i, msg in enumerate(messages):
        role = html.escape(str(msg.get("role", "")))
        content = html.escape(str(msg.get("content") or ""))
        actions = (msg.get("extra") or {}).get("actions") or []
        action_html = ""
        if actions:
            cmds = "<br/>".join(html.escape(str(a.get("command", a))) for a in actions)
            action_html = f"<div class='actions'><strong>actions</strong><br/>{cmds}</div>"
        msg_blocks.append(
            f"<section class='msg'><h3>#{i} {role}</h3>"
            f"<pre>{content}</pre>{action_html}</section>"
        )

    exit_status = html.escape(str(info.get("exit_status", "")))
    home = html.escape(home_href)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>Issue2Patch Trajectory</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; background: #0f1419; color: #e7ecf1; }}
    h1,h2,h3 {{ color: #7dd3fc; }}
    pre {{ white-space: pre-wrap; background: #1a2332; padding: 1rem; border-radius: 8px; }}
    .msg {{ margin-bottom: 1.5rem; border-left: 3px solid #334155; padding-left: 1rem; }}
    .actions {{ margin-top: .5rem; color: #86efac; }}
    code {{ background: #1e293b; padding: .1rem .35rem; border-radius: 4px; }}
    .nav {{ margin: 0 0 1.25rem; }}
    .nav a {{ color: #3db8a0; margin-right: 1rem; text-decoration: none; }}
    .nav a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <p class="nav">
    <a href="javascript:history.back()">← 返回上一页</a>
    <a href="{home}">返回控制台</a>
  </p>
  <h1>Issue2Patch · Trajectory</h1>
  <p>exit_status: <code>{exit_status}</code></p>
  <h2>Final plan (todos)</h2>
  <ul>{todo_rows or "<li>（无）</li>"}</ul>
  <h2>Messages</h2>
  {"".join(msg_blocks)}
</body>
</html>
"""
