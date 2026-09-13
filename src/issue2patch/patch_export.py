"""Export a unified diff from the workspace after the agent finishes."""

from __future__ import annotations

import subprocess
from pathlib import Path


def export_git_diff(workdir: Path, output_path: Path) -> str:
    """Write `git diff` (including untracked via add -N when possible) to output_path."""
    workdir = workdir.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not (workdir / ".git").exists():
        diff = _fallback_snapshot_note(workdir)
        output_path.write_text(diff, encoding="utf-8")
        return diff

    # Keep bytecode out of portfolio patches.
    ignore = workdir / ".gitignore"
    if ignore.exists():
        text = ignore.read_text(encoding="utf-8")
        if "__pycache__" not in text:
            ignore.write_text(text.rstrip() + "\n__pycache__/\n*.pyc\n", encoding="utf-8")
    else:
        ignore.write_text("__pycache__/\n*.pyc\n", encoding="utf-8")

    # Include untracked files in the diff when git supports intent-to-add.
    subprocess.run(
        ["git", "add", "-N", "."],
        cwd=workdir,
        check=False,
        capture_output=True,
        text=True,
    )
    proc = subprocess.run(
        ["git", "diff", "HEAD", "--", ".", ":(exclude)**/__pycache__/**", ":(exclude)*.pyc"],
        cwd=workdir,
        check=False,
        capture_output=True,
        text=True,
    )
    diff = proc.stdout or ""
    if not diff.strip():
        proc = subprocess.run(
            ["git", "diff", "--", ".", ":(exclude)**/__pycache__/**", ":(exclude)*.pyc"],
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )
        diff = proc.stdout or ""
    output_path.write_text(diff, encoding="utf-8")
    return diff


def _fallback_snapshot_note(workdir: Path) -> str:
    return (
        f"# No .git in {workdir}\n"
        "# Initialize git in the workspace to export a real patch, e.g.\n"
        "#   git init && git add -A && git commit -m init\n"
    )
