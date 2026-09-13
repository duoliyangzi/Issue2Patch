"""Offline deterministic model for end-to-end demos without an API key."""

from __future__ import annotations

from minisweagent.models.test_models import DeterministicModel, make_output


def build_offline_fixer_model(verify_cmd: str = "python -m pytest -q") -> DeterministicModel:
    """Return a scripted model that fixes examples/buggy_calc style bugs."""
    # Cross-platform: LocalEnvironment uses shell=True (cmd on Windows).
    fix_cmd = (
        "python -c \""
        "from pathlib import Path;"
        "p=Path('calc.py');"
        "t=p.read_text(encoding='utf-8');"
        "p.write_text(t.replace('return a * b','return a + b'),encoding='utf-8');"
        "print('fixed add()')"
        "\""
    )
    outputs = [
        make_output(
            content=(
                "I will plan and then inspect the workspace.\n\n"
                "```todos\n"
                "- [~] locate relevant files\n"
                "- [ ] reproduce the bug\n"
                "- [ ] implement the fix\n"
                "- [ ] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": "python -c \"import os; print(chr(10).join(os.listdir('.')))\""}],
            cost=0.0,
        ),
        make_output(
            content=(
                "Reading calc.py and updating the plan.\n\n"
                "```todos\n"
                "- [x] locate relevant files\n"
                "- [~] reproduce the bug\n"
                "- [ ] implement the fix\n"
                "- [ ] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": "python -c \"print(open('calc.py',encoding='utf-8').read())\""}],
            cost=0.0,
        ),
        make_output(
            content=(
                "Reproducing with the verify command.\n\n"
                "```todos\n"
                "- [x] locate relevant files\n"
                "- [~] reproduce the bug\n"
                "- [ ] implement the fix\n"
                "- [ ] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": verify_cmd}],
            cost=0.0,
        ),
        make_output(
            content=(
                "Bug confirmed: add() multiplies. Applying a minimal fix.\n\n"
                "```todos\n"
                "- [x] locate relevant files\n"
                "- [x] reproduce the bug\n"
                "- [~] implement the fix\n"
                "- [ ] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": fix_cmd}],
            cost=0.0,
        ),
        make_output(
            content=(
                "Re-running verify.\n\n"
                "```todos\n"
                "- [x] locate relevant files\n"
                "- [x] reproduce the bug\n"
                "- [x] implement the fix\n"
                "- [~] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": verify_cmd}],
            cost=0.0,
        ),
        make_output(
            content=(
                "All green. Submitting.\n\n"
                "```todos\n"
                "- [x] locate relevant files\n"
                "- [x] reproduce the bug\n"
                "- [x] implement the fix\n"
                "- [x] run verify command and confirm green\n"
                "```\n"
            ),
            actions=[{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}],
            cost=0.0,
        ),
    ]
    return DeterministicModel(outputs=outputs, model_name="issue2patch-offline", cost_per_call=0.0)
