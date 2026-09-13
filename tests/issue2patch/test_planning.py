"""Unit tests for todo planning parser (no LLM required)."""

from issue2patch.planning import latest_todos_from_messages, parse_todos


def test_parse_todos_block():
    text = """
I will start by locating files.

```todos
- [~] locate relevant files
- [ ] reproduce the bug
- [x] read issue
```
"""
    todos = parse_todos(text)
    assert todos is not None
    assert len(todos) == 3
    assert todos[0].status == "in_progress"
    assert todos[1].status == "pending"
    assert todos[2].status == "completed"


def test_latest_todos_from_messages():
    messages = [
        {"role": "assistant", "content": "```todos\n- [ ] a\n```"},
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "```todos\n- [x] a\n- [~] b\n```"},
    ]
    latest = latest_todos_from_messages(messages)
    assert latest == [
        {"text": "a", "status": "completed"},
        {"text": "b", "status": "in_progress"},
    ]
