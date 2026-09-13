"""Parse and track structured TODO plans from agent messages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

TODO_BLOCK_RE = re.compile(r"```todos\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
TODO_LINE_RE = re.compile(
    r"^\s*[-*]\s*\[(?P<mark>[ xX~])\]\s*(?P<text>.+?)\s*$",
    re.MULTILINE,
)


@dataclass
class TodoItem:
    text: str
    status: str  # pending | in_progress | completed

    def to_dict(self) -> dict:
        return asdict(self)


def _mark_to_status(mark: str) -> str:
    mark = mark.lower()
    if mark == "x":
        return "completed"
    if mark == "~":
        return "in_progress"
    return "pending"


def parse_todos(text: str) -> list[TodoItem] | None:
    """Return todos from the last ```todos``` block, or None if absent."""
    if not text:
        return None
    blocks = TODO_BLOCK_RE.findall(text)
    if not blocks:
        return None
    items: list[TodoItem] = []
    for match in TODO_LINE_RE.finditer(blocks[-1]):
        items.append(
            TodoItem(
                text=match.group("text").strip(),
                status=_mark_to_status(match.group("mark")),
            )
        )
    return items or None


def latest_todos_from_messages(messages: list[dict]) -> list[dict]:
    """Scan messages newest-first and return the latest parsed todo list."""
    for message in reversed(messages):
        content = message.get("content") or ""
        if not isinstance(content, str):
            continue
        todos = parse_todos(content)
        if todos is not None:
            return [t.to_dict() for t in todos]
    return []
