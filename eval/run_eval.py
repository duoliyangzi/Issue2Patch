"""Run Issue2Patch on a small self-built bugfix suite and emit a report."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=False)

from issue2patch.runner import run_fix  # noqa: E402

app = typer.Typer(add_completion=False)
console = Console()


def _materialize_case(case: dict, work_root: Path) -> Path:
    workdir = work_root / case["id"]
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    for rel, content in case["files"].items():
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (workdir / "issue.md").write_text(case["issue"], encoding="utf-8")
    subprocess.run(["git", "init"], cwd=workdir, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"init {case['id']}"],
        cwd=workdir,
        check=True,
        capture_output=True,
    )
    return workdir


def _verify(workdir: Path, cmd: str) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=workdir,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "passed": proc.returncode == 0,
    }


@app.command()
def main(
    cases_file: Path = typer.Option(REPO_ROOT / "eval" / "cases.json", "--cases"),
    out_dir: Path = typer.Option(REPO_ROOT / "eval" / "output", "--out"),
    limit: int = typer.Option(0, "--limit", help="Only first N cases (0=all)"),
    offline: bool = typer.Option(False, "--offline", help="Scripted fixer (add_mul only reliably)"),
    step_limit: int = typer.Option(20, "--step-limit"),
    ids: str = typer.Option("", "--ids", help="Comma-separated case ids"),
) -> None:
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    if ids.strip():
        wanted = {x.strip() for x in ids.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if limit > 0:
        cases = cases[:limit]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = out_dir / stamp
    work_root = run_root / "workspaces"
    agent_root = run_root / "agent_runs"
    run_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for case in cases:
        console.print(f"[cyan]Case[/] {case['id']} · {case['title']}")
        workdir = _materialize_case(case, work_root)
        before = _verify(workdir, case["verify_cmd"])
        if before["passed"]:
            console.print("[yellow]skip[/] verify already green before agent")
            results.append(
                {
                    "id": case["id"],
                    "title": case["title"],
                    "skipped": True,
                    "reason": "already_green",
                }
            )
            continue

        case_out = agent_root / case["id"]
        t0 = time.time()
        try:
            agent_result = run_fix(
                workdir=workdir,
                task=case["issue"],
                verify_cmd=case["verify_cmd"],
                sandbox="local",
                out_dir=case_out,
                step_limit=step_limit,
                cost_limit=0.0,
                offline=offline and case["id"] == "add_mul",
            )
            error = None
        except Exception as e:
            agent_result = {"exit_status": type(e).__name__}
            error = str(e)
        elapsed = round(time.time() - t0, 1)
        after = _verify(workdir, case["verify_cmd"])
        row = {
            "id": case["id"],
            "title": case["title"],
            "exit_status": agent_result.get("exit_status"),
            "verify_passed": after["passed"],
            "resolved": bool(after["passed"]),
            "elapsed_sec": elapsed,
            "api_calls": (agent_result.get("api_calls") or {}).get("api_calls"),
            "final_todos": agent_result.get("final_todos"),
            "error": error,
            "verify_stdout_tail": after.get("stdout"),
        }
        results.append(row)
        console.print(
            f"  -> resolved={row['resolved']} exit={row['exit_status']} time={elapsed}s"
        )

    resolved = sum(1 for r in results if r.get("resolved"))
    attempted = sum(1 for r in results if not r.get("skipped"))
    rate = (resolved / attempted) if attempted else 0.0
    report = {
        "generated_at": stamp,
        "model": os.getenv("ISSUE2PATCH_MODEL"),
        "offline": offline,
        "step_limit": step_limit,
        "n_cases": len(results),
        "n_attempted": attempted,
        "n_resolved": resolved,
        "resolve_rate": round(rate, 4),
        "results": results,
    }
    (run_root / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = _render_markdown(report)
    (run_root / "REPORT.md").write_text(md, encoding="utf-8")
    latest = out_dir / "LATEST_REPORT.md"
    latest.write_text(md, encoding="utf-8")
    console.print(f"[green]resolve_rate[/] {resolved}/{attempted} = {rate:.0%}")
    console.print(f"[green]report[/] {run_root / 'REPORT.md'}")


def _render_markdown(report: dict) -> str:
    lines = [
        "# Issue2Patch Eval Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- model: `{report.get('model')}`",
        f"- offline: `{report.get('offline')}`",
        f"- step_limit: `{report.get('step_limit')}`",
        f"- resolve_rate: **{report['n_resolved']}/{report['n_attempted']} "
        f"= {report['resolve_rate']:.0%}**",
        "",
        "| id | title | resolved | exit_status | elapsed_s |",
        "|----|-------|----------|-------------|-----------|",
    ]
    for r in report["results"]:
        if r.get("skipped"):
            lines.append(f"| `{r['id']}` | {r['title']} | skipped | - | - |")
            continue
        lines.append(
            f"| `{r['id']}` | {r['title']} | {'yes' if r.get('resolved') else 'no'} | "
            f"{r.get('exit_status')} | {r.get('elapsed_sec')} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "Self-built mini suite for portfolio evaluation "
        "(not SWE-bench). Failures are kept for interview discussion."
    )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    app()
