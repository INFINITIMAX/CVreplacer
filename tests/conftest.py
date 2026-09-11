"""Fixtures comune pentru testele stratului de stocare.

Fiecare test primeste o baza SQLite temporara, proprie, creata prin
storage.connect(). Nu se atinge niciodata data/.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from cvreplacer.storage import RawJob, connect
from cvreplacer.storage.models import JobRow


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """O conexiune noua, pe o baza temporara unica per test."""
    db_path = tmp_path / "test.db"
    connection = connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def make_job(
    url: str = "https://exemplu.test/1",
    title: str = "Dezvoltator Python",
    company: str = "Compania Exemplu SRL",
    city: str | None = "Cluj-Napoca",
    remote: str | None = "hybrid",
    source: str = "peviitor",
    raw_text: str | None = None,
) -> RawJob:
    """Fabrica de RawJob cu date inventate, fara nimic personal."""
    return RawJob(
        url=url,
        title=title,
        company=company,
        city=city,
        remote=remote,
        source=source,
        raw_text=raw_text,
    )


def make_job_row(
    url: str = "https://exemplu.test/1",
    title: str = "Dezvoltator Python",
    company: str = "Compania Exemplu SRL",
    city: str | None = "Cluj-Napoca",
    remote: str | None = "hybrid",
    source: str = "peviitor",
    first_seen: str = "2026-01-01T00:00:00Z",
    last_seen: str = "2026-01-01T00:00:00Z",
    missing_runs: int = 0,
    status: str = "active",
    fetch_status: str | None = None,
    raw_text: str | None = None,
    fetched_at: str | None = None,
) -> JobRow:
    """Fabrica de JobRow pentru testele filtrelor (E4). Date inventate, fara nimic personal."""
    return JobRow(
        url=url,
        title=title,
        company=company,
        city=city,
        remote=remote,
        source=source,
        first_seen=first_seen,
        last_seen=last_seen,
        missing_runs=missing_runs,
        status=status,
        fetch_status=fetch_status,
        raw_text=raw_text,
        fetched_at=fetched_at,
    )
