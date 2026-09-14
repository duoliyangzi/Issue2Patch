"""Shared Issue2Patch execution used by CLI and Web UI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from issue2patch.patch_export import export_git_diff
from issue2patch.trajectory import write_trajectory_files

PACKAGE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    path = PACKAGE_DIR / "config" / "issue2patch.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def default_model_name() -> str:
    return (
        os.getenv("ISSUE2PATCH_MODEL")
        or os.getenv("MSWEA_MODEL_NAME")
        or "openai/qwen3.8-flash"
    )


def default_engine() -> str:
    return (os.getenv("ISSUE2PATCH_ENGINE") or "langchain").strip().lower()


def run_fix(
    *,
    workdir: Path,
    task: str,
    verify_cmd: str = "python -m pytest -q",
    model_name: str | None = None,
    sandbox: str = "local",
    docker_image: str = "python:3.12-slim",
    out_dir: Path,
    step_limit: int = 40,
    cost_limit: float = 5.0,
    offline: bool = False,
    engine: str | None = None,
) -> dict[str, Any]:
    """Run agent and return paths + status for UI/CLI.

    engine:
      - langchain (default on feature/langchain-agent): LangGraph create_react_agent
      - mini: legacy mini-swe-agent harness
    """
    workdir = workdir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = (engine or default_engine()).lower()
    if offline:
        engine = "mini"
    model_name = model_name or ("issue2patch-offline" if offline else default_model_name())

    if engine == "langchain":
        if sandbox != "local":
            raise ValueError("langchain engine currently supports sandbox=local only")
        from issue2patch.langchain_agent import run_langchain_fix

        lc = run_langchain_fix(
            workdir=workdir,
            task=task,
            verify_cmd=verify_cmd,
            model_name=model_name,
            out_dir=out_dir,
            step_limit=step_limit,
        )
        data = lc["data"]
        json_path, html_path = write_trajectory_files(data, out_dir)
        patch_path = out_dir / "fix.patch"
        diff = export_git_diff(workdir, patch_path)
        return {
            "exit_status": lc.get("exit_status"),
            "model": model_name,
            "engine": "langchain",
            "workdir": str(workdir),
            "out_dir": str(out_dir),
            "trajectory_json": str(json_path),
            "trajectory_html": str(html_path),
            "patch_path": str(patch_path),
            "patch_chars": len(diff),
            "patch_preview": diff[:4000],
            "final_todos": lc.get("final_todos") or [],
            "api_calls": lc.get("api_calls") or {},
        }

    # ---- legacy mini-swe-agent path ----
    from issue2patch.agent import PlanningAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.environments.local import LocalEnvironment
    from minisweagent.models.litellm_model import LitellmModel

    cfg = load_config()
    agent_kwargs = dict(cfg["agent"])
    agent_kwargs["step_limit"] = step_limit
    agent_kwargs["cost_limit"] = 0.0 if offline else cost_limit
    agent_kwargs.pop("mode", None)

    traj_json = out_dir / "trajectory.json"
    agent_kwargs["output_path"] = traj_json

    env_cfg = dict(cfg.get("environment") or {})
    env_env = dict(env_cfg.get("env") or {})
    timeout = int(env_cfg.get("timeout") or 60)

    if sandbox == "docker":
        mount = f"{workdir}:{workdir}"
        environment = DockerEnvironment(
            image=docker_image,
            cwd=str(workdir),
            env=env_env,
            run_args=["--rm", "-v", mount],
            timeout=timeout,
        )
    elif sandbox == "local":
        environment = LocalEnvironment(cwd=str(workdir), env=env_env, timeout=timeout)
    else:
        raise ValueError("sandbox must be local or docker")

    if offline:
        from issue2patch.offline_model import build_offline_fixer_model

        model = build_offline_fixer_model(verify_cmd=verify_cmd)
    else:
        model_kwargs = dict((cfg.get("model") or {}).get("model_kwargs") or {})
        model = LitellmModel(
            model_name=model_name,
            model_kwargs=model_kwargs,
            observation_template=(cfg.get("model") or {}).get("observation_template"),
            format_error_template=(cfg.get("model") or {}).get("format_error_template"),
        )

    agent = PlanningAgent(model, environment, **agent_kwargs)
    result = agent.run(task, workdir=str(workdir), verify_cmd=verify_cmd)
    data = agent.save(traj_json)
    json_path, html_path = write_trajectory_files(data, out_dir)
    patch_path = out_dir / "fix.patch"
    diff = export_git_diff(workdir, patch_path)
    todos = (data.get("issue2patch") or {}).get("final_todos") or []

    return {
        "exit_status": result.get("exit_status"),
        "model": model_name,
        "engine": "mini",
        "workdir": str(workdir),
        "out_dir": str(out_dir),
        "trajectory_json": str(json_path),
        "trajectory_html": str(html_path),
        "patch_path": str(patch_path),
        "patch_chars": len(diff),
        "patch_preview": diff[:4000],
        "final_todos": todos,
        "api_calls": (data.get("info") or {}).get("model_stats") or {},
    }


def materialize_demo(target: Path) -> Path:
    """Reset demo workspace to the intentional buggy template (overwrite)."""
    import subprocess

    src = PACKAGE_DIR.parent.parent / "examples" / "buggy_calc"
    if not src.exists():
        raise FileNotFoundError(f"Demo source not found: {src}")
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    for name in ("calc.py", "issue.md"):
        (target / name).write_bytes((src / name).read_bytes())
    tests_src = src / "tests"
    tests_dst = target / "tests"
    tests_dst.mkdir(parents=True, exist_ok=True)
    for path in tests_src.rglob("*"):
        if path.is_file():
            dest = tests_dst / path.relative_to(tests_src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())

    calc_text = (target / "calc.py").read_text(encoding="utf-8")
    if "return a * b" not in calc_text:
        raise RuntimeError("Demo reset failed: calc.py is not in buggy state")

    if not (target / ".git").exists():
        subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=target, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init buggy demo"],
            cwd=target,
            check=True,
            capture_output=True,
        )
    else:
        subprocess.run(["git", "add", "-A"], cwd=target, check=False, capture_output=True)

    return target
