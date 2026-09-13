"""Planning-aware agent wrapper around mini-swe-agent DefaultAgent."""

from __future__ import annotations

from minisweagent.agents.default import DefaultAgent

from issue2patch.planning import latest_todos_from_messages


class PlanningAgent(DefaultAgent):
    """DefaultAgent + todo plan snapshots in the saved trajectory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.todo_history: list[dict] = []

    def step(self) -> list[dict]:
        result = super().step()
        todos = latest_todos_from_messages(self.messages)
        if todos:
            snapshot = {
                "step": self.n_calls,
                "todos": todos,
            }
            if not self.todo_history or self.todo_history[-1].get("todos") != todos:
                self.todo_history.append(snapshot)
        return result

    def serialize(self, *extra_dicts) -> dict:
        return super().serialize(
            {
                "issue2patch": {
                    "todo_history": self.todo_history,
                    "final_todos": latest_todos_from_messages(self.messages),
                }
            },
            *extra_dicts,
        )
