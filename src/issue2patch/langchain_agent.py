"""LangChain / LangGraph ReAct coding agent for Issue2Patch."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from issue2patch.planning import latest_todos_from_messages, parse_todos


SYSTEM_PROMPT = """你是 Issue2Patch，一个用工具修代码缺陷的 Coding Agent。
工作区目录已经固定；所有相对路径都相对于该工作区。

必须遵循：
1. 先用 update_todos 写出计划（locate / reproduce / fix / verify）。
2. 用 list_files / read_file / run_command 定位并复现问题。
3. 用 write_file 或 run_command 做最小修改。
4. 用验证命令确认测试通过。
5. 完成后调用 submit_fix，summary 用一句话说明改动。

不要编造文件内容；先读再改。优先小改动。
"""


@dataclass
class RunState:
    workdir: Path
    verify_cmd: str
    todos: list[dict] = field(default_factory=list)
    todo_history: list[dict] = field(default_factory=list)
    submitted: bool = False
    submission: str = ""
    step: int = 0


def _safe_path(workdir: Path, rel: str) -> Path:
    workdir = workdir.resolve()
    path = (workdir / rel).resolve()
    if workdir not in path.parents and path != workdir:
        raise ValueError(f"path escapes workdir: {rel}")
    return path


def build_tools(state: RunState):
    workdir = state.workdir

    @tool
    def list_files(relative_dir: str = ".") -> str:
        """List files under a relative directory inside the workspace."""
        root = _safe_path(workdir, relative_dir)
        if not root.exists():
            return f"missing: {relative_dir}"
        lines = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts:
                lines.append(str(p.relative_to(workdir)).replace("\\", "/"))
        return "\n".join(lines[:200]) or "(empty)"

    @tool
    def read_file(relative_path: str) -> str:
        """Read a text file from the workspace."""
        path = _safe_path(workdir, relative_path)
        if not path.exists():
            return f"missing file: {relative_path}"
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > 12000:
            return text[:6000] + "\n...\n" + text[-6000:]
        return text

    @tool
    def write_file(relative_path: str, content: str) -> str:
        """Write/overwrite a text file in the workspace."""
        path = _safe_path(workdir, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"wrote {relative_path} ({len(content)} chars)"

    @tool
    def run_command(command: str) -> str:
        """Run a shell command inside the workspace (cwd=workdir)."""
        proc = subprocess.run(
            command,
            cwd=workdir,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        if len(out) > 12000:
            out = out[:6000] + "\n...\n" + out[-6000:]
        return json.dumps({"returncode": proc.returncode, "output": out}, ensure_ascii=False)

    @tool
    def update_todos(todos_markdown: str) -> str:
        """Update the task plan. Pass a markdown checklist, e.g.
        - [~] locate files
        - [ ] reproduce
        - [ ] fix
        - [ ] verify
        Marks: [ ] pending, [~] in_progress, [x] completed.
        """
        block = "```todos\n" + todos_markdown.strip() + "\n```"
        items = parse_todos(block) or []
        state.todos = [t.to_dict() for t in items]
        state.step += 1
        state.todo_history.append({"step": state.step, "todos": list(state.todos)})
        return "todos updated: " + json.dumps(state.todos, ensure_ascii=False)

    @tool
    def submit_fix(summary: str) -> str:
        """Call this when the bug is fixed and verify command passes."""
        state.submitted = True
        state.submission = summary
        return f"submitted: {summary}"

    return [list_files, read_file, write_file, run_command, update_todos, submit_fix]


def _model_id(model_name: str) -> str:
    name = model_name.strip()
    if name.startswith("openai/"):
        return name.split("/", 1)[1]
    if "/" in name and not name.startswith("gpt-"):
        # litellm-style provider/model -> use model part for OpenAI-compatible gateways
        return name.split("/", 1)[1]
    return name


def build_chat_model(model_name: str) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE")
    kwargs: dict[str, Any] = {
        "model": _model_id(model_name),
        "temperature": 0,
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def messages_to_trajectory(messages: list[BaseMessage]) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        else:
            role = getattr(msg, "type", "unknown")
        content = msg.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        extra: dict[str, Any] = {}
        if isinstance(msg, AIMessage) and msg.tool_calls:
            actions = []
            for tc in msg.tool_calls:
                name = tc.get("name")
                args = tc.get("args") or {}
                if name == "run_command":
                    actions.append({"command": args.get("command", "")})
                else:
                    actions.append({"command": f"{name}({json.dumps(args, ensure_ascii=False)})"})
            extra["actions"] = actions
        out.append({"role": role, "content": content or "", "extra": extra})
    return out


def run_langchain_fix(
    *,
    workdir: Path,
    task: str,
    verify_cmd: str,
    model_name: str,
    out_dir: Path,
    step_limit: int = 40,
) -> dict[str, Any]:
    workdir = workdir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    state = RunState(workdir=workdir, verify_cmd=verify_cmd)
    tools = build_tools(state)
    llm = build_chat_model(model_name)
    agent = create_react_agent(llm, tools)

    user_prompt = (
        f"## Issue\n{task}\n\n"
        f"## Workspace\n{workdir}\n\n"
        f"## Verify command\n{verify_cmd}\n\n"
        "请开始修复。记得先 update_todos，最后 submit_fix。"
    )

    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        },
        config={"recursion_limit": max(step_limit * 2, 20)},
    )
    messages: list[BaseMessage] = list(result.get("messages") or [])
    traj_messages = messages_to_trajectory(messages)

    # Also harvest todos from assistant text if tool wasn't used.
    if not state.todos:
        fake = [{"role": m["role"], "content": m["content"]} for m in traj_messages]
        state.todos = latest_todos_from_messages(fake)

    exit_status = "Submitted" if state.submitted else "Completed"
    data = {
        "messages": traj_messages,
        "info": {
            "exit_status": exit_status,
            "submission": state.submission,
            "model_stats": {"api_calls": sum(1 for m in messages if isinstance(m, AIMessage))},
            "config": {"engine": "langchain-langgraph", "model": model_name},
        },
        "issue2patch": {
            "todo_history": state.todo_history,
            "final_todos": state.todos,
            "engine": "langchain",
        },
    }
    traj_json = out_dir / "trajectory.json"
    traj_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "exit_status": exit_status,
        "data": data,
        "traj_json": traj_json,
        "final_todos": state.todos,
        "api_calls": data["info"]["model_stats"],
        "model": model_name,
    }
