"""Runtime helpers for local teaching episodes."""
from __future__ import annotations

from pathlib import Path
import sqlite3

from .generator import load_session
from .task import Task
from .tools import make_tools

TOOLS = make_tools()


def prepare(task: Task, workdir: Path):
    workdir.mkdir(parents=True, exist_ok=True)
    load_session(task.seed, workdir, difficulty=task.difficulty)
    paths = (workdir / "teaching.db", workdir / "teaching_state.db")
    for path in paths:
        sqlite3.connect(path).close()
    assertions = workdir / "assertions.sql"
    assertions.write_text("-- Teaching score is computed from the hidden visual manifest.\n")
    return paths[0], paths[1], assertions


def make_api(task: Task, workdir: Path, artifacts_dir: Path | None = None):
    return load_session(task.seed, workdir, difficulty=task.difficulty)
