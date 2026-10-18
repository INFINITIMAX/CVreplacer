"""Structurile de date ale stratului de stocare.

O dataclass per tabel, plus RawJob (contractul de intrare din surse)
si SeenResult (rezultatul lui upsert_seen).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawJob:
    """Ce produce orice sursa, inainte sa ajunga in baza de date."""

    url: str
    title: str
    company: str
    city: str | None
    remote: str | None  # on-site | hybrid | remote
    source: str  # peviitor | freehire | manual
    raw_text: str | None = None


@dataclass(frozen=True)
class JobRow:
    """Un rand din tabela jobs."""

    url: str
    title: str
    company: str
    city: str | None
    remote: str | None
    source: str
    first_seen: str
    last_seen: str
    missing_runs: int
    status: str  # active | dead
    fetch_status: str | None
    raw_text: str | None
    fetched_at: str | None


@dataclass(frozen=True)
class ScoreRow:
    """Un rand din tabela scores."""

    id: int
    url: str
    prompt_version: str
    fit: float
    vetoed: bool
    veto_reason: str | None
    requirements_json: str
    usage_json: str | None
    scored_at: str


@dataclass(frozen=True)
class Application:
    """Un rand din tabela applications."""

    url: str
    applied_at: str
    note: str | None
    outcome: str  # pending | rejected | interview | offer | ghosted


@dataclass(frozen=True)
class Run:
    """Un rand din tabela runs."""

    id: int
    started_at: str
    finished_at: str | None
    n_harvested: int | None
    n_filtered: int | None
    n_scored: int | None
    cost_usd: float | None
    notes: str | None


@dataclass(frozen=True)
class SeenResult:
    """Rezultatul lui upsert_seen: cate anunturi noi / actualizate / reinviate."""

    new: int
    updated: int
    revived: int
