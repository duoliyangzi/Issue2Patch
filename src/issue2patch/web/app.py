"""Local Web UI for Issue2Patch."""

from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(Path.cwd() / ".env", override=False)

from issue2patch.runner import default_engine, default_model_name, materialize_demo, run_fix

STATIC_DIR = Path(__file__).resolve().parent / "static"
RUNS_ROOT = _REPO_ROOT / "runs" / "web"

app = FastAPI(title="Issue2Patch UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class RunRequest(BaseModel):
    workdir: str = Field(..., description="Absolute path to the git workspace")
    issue: str = Field(..., description="Issue / bug description")
    verify_cmd: str = "python -m pytest -q"
    model: str | None = None
    sandbox: str = "local"
    offline: bool = False
    step_limit: int = 25
    engine: str = "langchain"


class DemoRequest(BaseModel):
    target: str | None = None


def _set_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _jobs.setdefault(job_id, {})
        job.update(kwargs)


def _get_job(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return dict(job)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/defaults")
def defaults() -> dict:
    demo = _REPO_ROOT / "examples" / "buggy_calc_run"
    issue = ""
    issue_path = demo / "issue.md"
    if issue_path.exists():
        issue = issue_path.read_text(encoding="utf-8")
    return {
        "workdir": str(demo) if demo.exists() else str(_REPO_ROOT / "examples" / "buggy_calc_run"),
        "issue": issue
        or "# Bug\nDescribe the failing behavior and how to reproduce.\n",
        "verify_cmd": "python -m pytest -q",
        "model": default_model_name(),
        "engine": default_engine(),
        "repo_root": str(_REPO_ROOT),
    }


@app.post("/api/demo")
def prepare_demo(body: DemoRequest) -> dict:
    target = Path(body.target) if body.target else _REPO_ROOT / "examples" / "buggy_calc_run"
    path = materialize_demo(target)
    issue = (path / "issue.md").read_text(encoding="utf-8")
    calc = (path / "calc.py").read_text(encoding="utf-8")
    return {
        "workdir": str(path),
        "issue": issue,
        "verify_cmd": "python -m pytest -q",
        "calc_preview": calc,
        "buggy": "return a * b" in calc,
    }


@app.post("/api/run")
def start_run(body: RunRequest) -> dict:
    workdir = Path(body.workdir)
    if not workdir.is_dir():
        raise HTTPException(400, f"workdir not found: {workdir}")
    if not body.issue.strip():
        raise HTTPException(400, "issue is empty")

    job_id = uuid.uuid4().hex[:10]
    out_dir = RUNS_ROOT / job_id
    _set_job(
        job_id,
        status="running",
        started_at=time.time(),
        workdir=str(workdir.resolve()),
        out_dir=str(out_dir),
        error=None,
        result=None,
    )

    def _worker() -> None:
        try:
            result = run_fix(
                workdir=workdir,
                task=body.issue,
                verify_cmd=body.verify_cmd,
                model_name=body.model,
                sandbox=body.sandbox,
                out_dir=out_dir,
                step_limit=body.step_limit,
                cost_limit=0.0,
                offline=body.offline,
                engine=body.engine,
            )
            _set_job(job_id, status="done", finished_at=time.time(), result=result)
        except Exception as e:
            _set_job(
                job_id,
                status="error",
                finished_at=time.time(),
                error=f"{type(e).__name__}: {e}",
                traceback=traceback.format_exc(),
            )

    threading.Thread(target=_worker, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return _get_job(job_id)


@app.get("/runs/{job_id}/trajectory.html")
def trajectory_html(job_id: str) -> HTMLResponse:
    path = RUNS_ROOT / job_id / "trajectory.html"
    if not path.exists():
        raise HTTPException(404, "trajectory not ready")
    raw = path.read_text(encoding="utf-8")
    nav = """
<style>
  .i2p-topnav {
    position: sticky; top: 0; z-index: 99;
    display: flex; gap: 1rem; align-items: center;
    padding: .75rem 1rem; margin: -2rem -2rem 1.25rem;
    background: #0b1220; border-bottom: 1px solid #2a3645;
    font-family: ui-sans-serif, system-ui, sans-serif;
  }
  .i2p-topnav a {
    color: #3db8a0; text-decoration: none; font-weight: 600;
  }
  .i2p-topnav a:hover { text-decoration: underline; }
</style>
<div class="i2p-topnav">
  <a href="/">← 返回控制台</a>
  <a href="javascript:history.back()">返回上一页</a>
</div>
"""
    if "i2p-topnav" in raw:
        html = raw
    elif "<body>" in raw:
        html = raw.replace("<body>", "<body>\n" + nav, 1)
    else:
        html = nav + raw
    return HTMLResponse(html)


@app.get("/runs/{job_id}/fix.patch")
def fix_patch(job_id: str) -> FileResponse:
    path = RUNS_ROOT / job_id / "fix.patch"
    if not path.exists():
        raise HTTPException(404, "patch not ready")
    return FileResponse(path, media_type="text/plain")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "issue2patch.web.app:app",
        host="127.0.0.1",
        port=int(os.getenv("ISSUE2PATCH_UI_PORT", "8765")),
        reload=False,
    )


if __name__ == "__main__":
    main()
