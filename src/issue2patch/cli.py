"""Issue2Patch CLI: issue text/file → planning agent → patch + trajectory."""

from __future__ import annotations

import os
from pathlib import Path

# Quiet mini-swe-agent banner when launching via Issue2Patch.
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from dotenv import load_dotenv

# Load repo-local .env before importing model clients.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(Path.cwd() / ".env", override=False)

import typer
from rich.console import Console

app = typer.Typer(
    name="issue2patch",
    help="Issue → plan → sandbox fix → export patch + trajectory",
    add_completion=False,
)
console = Console()


def _load_issue(issue: str | None, issue_file: Path | None) -> str:
    if issue_file is not None:
        return issue_file.read_text(encoding="utf-8")
    if issue:
        return issue
    raise typer.BadParameter("Provide --issue or --issue-file")


def _default_model() -> str:
    return (
        os.getenv("ISSUE2PATCH_MODEL")
        or os.getenv("MSWEA_MODEL_NAME")
        or "dashscope/qwen-plus"
    )


@app.command("run")
def run(
    workdir: Path = typer.Option(
        ...,
        "--workdir",
        "-w",
        help="Repository / workspace to fix (prefer a git repo)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    issue: str | None = typer.Option(None, "--issue", "-i", help="Issue text"),
    issue_file: Path | None = typer.Option(
        None,
        "--issue-file",
        "-f",
        help="Path to issue markdown/text",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    verify_cmd: str = typer.Option(
        "pytest -q",
        "--verify-cmd",
        "-v",
        help="Command used to reproduce / verify the fix",
    ),
    model_name: str = typer.Option(
        None,
        "--model",
        "-m",
        help="LiteLLM model id (default: ISSUE2PATCH_MODEL / dashscope/qwen-plus)",
    ),
    sandbox: str = typer.Option(
        "local",
        "--sandbox",
        "-s",
        help="Execution sandbox: local | docker",
    ),
    docker_image: str = typer.Option(
        "python:3.12-slim",
        "--docker-image",
        help="Image when --sandbox docker",
    ),
    out_dir: Path = typer.Option(
        Path("runs") / "latest",
        "--out",
        "-o",
        help="Directory for trajectory + patch",
        resolve_path=True,
    ),
    step_limit: int = typer.Option(40, "--step-limit", help="Max model calls"),
    cost_limit: float = typer.Option(5.0, "--cost-limit", help="Max estimated cost"),
    yolo: bool = typer.Option(True, "--yolo/--confirm", help="Run without per-step confirm"),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Run without LLM API (scripted fixer for the buggy_calc demo)",
    ),
) -> None:
    """Run Issue2Patch on a workspace and export patch + trajectory."""
    from issue2patch.runner import run_fix

    task = _load_issue(issue, issue_file)
    model_name = model_name or ("issue2patch-offline" if offline else _default_model())

    if sandbox == "docker":
        console.print(f"[cyan]Sandbox:[/] docker ({docker_image})")
    elif sandbox == "local":
        console.print("[cyan]Sandbox:[/] local subprocess")
    else:
        raise typer.BadParameter("sandbox must be local or docker")

    if offline:
        console.print("[yellow]Mode:[/] offline (no API key; scripted agent)")

    console.print(f"[cyan]Model:[/] {model_name}")
    console.print(f"[cyan]Workdir:[/] {workdir}")
    console.print(f"[cyan]Verify:[/] {verify_cmd}")
    console.print("[cyan]Running agent…[/]")
    _ = yolo

    result = run_fix(
        workdir=workdir,
        task=task,
        verify_cmd=verify_cmd,
        model_name=model_name,
        sandbox=sandbox,
        docker_image=docker_image,
        out_dir=out_dir,
        step_limit=step_limit,
        cost_limit=cost_limit,
        offline=offline,
    )

    console.print(f"[green]exit_status:[/] {result.get('exit_status')}")
    console.print(f"[green]trajectory:[/] {result.get('trajectory_json')}")
    console.print(f"[green]replay:[/] {result.get('trajectory_html')}")
    console.print(f"[green]patch:[/] {result.get('patch_path')} ({result.get('patch_chars')} chars)")
    for t in result.get("final_todos") or []:
        console.print(f"  - [{t.get('status')}] {t.get('text')}")


@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """Open the local web UI in a browser-friendly server."""
    import uvicorn

    console.print(f"[green]Issue2Patch UI[/]  http://{host}:{port}")
    uvicorn.run("issue2patch.web.app:app", host=host, port=port, reload=False)


@app.command("init-demo")
def init_demo(
    target: Path = typer.Option(
        Path("examples/buggy_calc_run"),
        "--target",
        "-t",
        help="Where to materialize the demo repo",
        resolve_path=True,
    ),
) -> None:
    """Copy the bundled buggy calculator demo and git-init it."""
    from issue2patch.runner import materialize_demo

    path = materialize_demo(target)
    console.print(f"[green]Demo ready:[/] {path}")
    console.print("Open UI: issue2patch ui")
    console.print(
        "Or CLI:\n"
        f'  issue2patch run -w "{path}" -f "{path / "issue.md"}" '
        f'-v "python -m pytest -q" -o runs/demo'
    )


@app.callback()
def main() -> None:
    """Issue2Patch CLI."""


def app_main() -> None:
    # Allow `python -m issue2patch.cli`
    app()


if __name__ == "__main__":
    app_main()
