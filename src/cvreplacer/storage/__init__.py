"""Stratul de stocare: SQLite, fara ORM."""

from __future__ import annotations

from cvreplacer.storage.db import (
    age_days,
    connect,
    finish_run,
    list_active_jobs,
    mark_absent,
    mark_applied,
    save_fetch_result,
    save_score,
    start_run,
    upsert_seen,
)
from cvreplacer.storage.models import Application, JobRow, RawJob, Run, ScoreRow, SeenResult

__all__ = [
    "Application",
    "JobRow",
    "RawJob",
    "Run",
    "ScoreRow",
    "SeenResult",
    "age_days",
    "connect",
    "finish_run",
    "list_active_jobs",
    "mark_absent",
    "mark_applied",
    "save_fetch_result",
    "save_score",
    "start_run",
    "upsert_seen",
]
