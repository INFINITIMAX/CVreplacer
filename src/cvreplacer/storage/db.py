"""Deschiderea conexiunii si operatiile pe baza de date.

Nicio functie de aici nu atinge first_seen dupa ce a fost scris o data:
e singura sursa de adevar pentru prospetime.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from cvreplacer.storage import schema
from cvreplacer.storage.models import JobRow, RawJob, SeenResult


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


_JOB_FIELDS = tuple(JobRow.__dataclass_fields__)


def _job_row(row: sqlite3.Row) -> JobRow:
    # `.keys()` e obligatoriu aici: pe un sqlite3.Row, `k in row` cauta printre
    # VALORI, nu printre nume de coloana, si ar intoarce False pentru fiecare
    # camp. Verificat: r.keys() == ['a','b'] dar 'a' in r == False.
    return JobRow(**{k: row[k] for k in row.keys() if k in _JOB_FIELDS})  # noqa: SIM118


def list_active_jobs(conn: sqlite3.Connection, limit: int | None = None) -> list[JobRow]:
    """Anunturile inca active, cele mai noi intai dupa first_seen.

    Ordinea conteaza: cand exista un plafon, vrem anunturile proaspete, nu pe
    cele vechi la care oricum nu mai poti aplica.
    """
    sql = "SELECT * FROM jobs WHERE status = 'active' ORDER BY first_seen DESC"
    params: tuple[int, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [_job_row(r) for r in conn.execute(sql, params)]


def save_fetch_result(
    conn: sqlite3.Connection,
    url: str,
    *,
    raw_text: str | None,
    fetch_status: str,
    fetched_at: str | None = None,
) -> None:
    """Scrie rezultatul descarcarii pentru un anunt.

    Nu atinge first_seen, last_seen sau status: descarcarea spune ceva despre
    pagina anuntului, nu despre prezenta lui in index.
    """
    conn.execute(
        "UPDATE jobs SET raw_text = ?, fetch_status = ?, fetched_at = ? WHERE url = ?",
        (raw_text, fetch_status, fetched_at or _now_iso(), url),
    )
    conn.commit()


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Deschide conexiunea, activeaza foreign_keys si aplica migrarile lipsa."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema.migrate(conn)
    return conn


def upsert_seen(conn: sqlite3.Connection, jobs: Iterable[RawJob], run_at: str) -> SeenResult:
    """Inregistreaza anunturile vazute la rularea curenta.

    url nou: insert cu first_seen = last_seen = run_at.
    url existent: doar last_seen si missing_runs = 0. first_seen nu se atinge.
    url existent si mort: reinviat -> status = active, missing_runs = 0.
    """
    new = 0
    updated = 0
    revived = 0
    for job in jobs:
        row = conn.execute("SELECT status FROM jobs WHERE url = ?", (job.url,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO jobs (url, title, company, city, remote, source,
                                   first_seen, last_seen, missing_runs, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')
                """,
                (
                    job.url,
                    job.title,
                    job.company,
                    job.city,
                    job.remote,
                    job.source,
                    run_at,
                    run_at,
                ),
            )
            new += 1
        elif row["status"] == "dead":
            conn.execute(
                "UPDATE jobs SET last_seen = ?, missing_runs = 0, status = 'active' WHERE url = ?",
                (run_at, job.url),
            )
            revived += 1
        else:
            conn.execute(
                "UPDATE jobs SET last_seen = ?, missing_runs = 0 WHERE url = ?",
                (run_at, job.url),
            )
            updated += 1
    conn.commit()
    return SeenResult(new=new, updated=updated, revived=revived)


def mark_absent(conn: sqlite3.Connection, seen_urls: set[str], run_at: str) -> int:
    """Creste missing_runs pentru anunturile active absente din rularea curenta.

    run_at nu e scris nicaieri (nu exista o astfel de coloana pe jobs);
    e primit doar ca sa pastreze semnatura ceruta si consistenta cu upsert_seen.
    """
    del run_at
    rows = conn.execute("SELECT url FROM jobs WHERE status = 'active'").fetchall()
    absent_urls = [row["url"] for row in rows if row["url"] not in seen_urls]

    dead_count = 0
    for url in absent_urls:
        conn.execute("UPDATE jobs SET missing_runs = missing_runs + 1 WHERE url = ?", (url,))
        row = conn.execute("SELECT missing_runs FROM jobs WHERE url = ?", (url,)).fetchone()
        if row["missing_runs"] >= 2:
            conn.execute("UPDATE jobs SET status = 'dead' WHERE url = ?", (url,))
            dead_count += 1
    conn.commit()
    return dead_count


def age_days(conn: sqlite3.Connection, url: str, now: str) -> float:
    """Vechimea reala a anuntului, calculata din first_seen, in zile.

    Poate fi negativa daca `now` precede `first_seen`. Nu tratam cazul ca eroare:
    e imposibil in fluxul normal, iar o exceptie ar ascunde o problema de ceas
    in loc s-o arate.
    """
    row = conn.execute("SELECT first_seen FROM jobs WHERE url = ?", (url,)).fetchone()
    if row is None:
        raise KeyError(f"url necunoscut in jobs: {url}")
    # Python 3.11+ parseaza direct sufixul Z, deci nu mai e nevoie de substitutie.
    first_seen = datetime.fromisoformat(row["first_seen"])
    current = datetime.fromisoformat(now)
    return (current - first_seen).total_seconds() / 86400


def save_score(
    conn: sqlite3.Connection,
    url: str,
    prompt_version: str,
    fit: float,
    vetoed: bool,
    veto_reason: str | None,
    requirements_json: str,
    usage_json: str | None,
    scored_at: str,
) -> None:
    """Upsert pe (url, prompt_version): o rescorare cu aceeasi versiune suprascrie."""
    conn.execute(
        """
        INSERT INTO scores (url, prompt_version, fit, vetoed, veto_reason,
                             requirements_json, usage_json, scored_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (url, prompt_version) DO UPDATE SET
            fit = excluded.fit,
            vetoed = excluded.vetoed,
            veto_reason = excluded.veto_reason,
            requirements_json = excluded.requirements_json,
            usage_json = excluded.usage_json,
            scored_at = excluded.scored_at
        """,
        (
            url,
            prompt_version,
            fit,
            int(vetoed),
            veto_reason,
            requirements_json,
            usage_json,
            scored_at,
        ),
    )
    conn.commit()


def mark_applied(conn: sqlite3.Connection, url: str, note: str | None = None) -> None:
    """Inregistreaza o aplicare. Rescrierea aceluiasi url ii actualizeaza data si nota."""
    conn.execute(
        """
        INSERT INTO applications (url, applied_at, note, outcome)
        VALUES (?, ?, ?, 'pending')
        ON CONFLICT (url) DO UPDATE SET
            applied_at = excluded.applied_at,
            note = excluded.note
        """,
        (url, _now_iso(), note),
    )
    conn.commit()


def start_run(conn: sqlite3.Connection) -> int:
    """Deschide o rulare noua si returneaza id-ul ei."""
    cursor = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (_now_iso(),))
    conn.commit()
    return cursor.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    n_harvested: int | None = None,
    n_filtered: int | None = None,
    n_scored: int | None = None,
    cost_usd: float | None = None,
    notes: str | None = None,
) -> None:
    """Inchide rularea run_id cu contoarele acumulate."""
    conn.execute(
        """
        UPDATE runs
        SET finished_at = ?, n_harvested = ?, n_filtered = ?, n_scored = ?,
            cost_usd = ?, notes = ?
        WHERE id = ?
        """,
        (_now_iso(), n_harvested, n_filtered, n_scored, cost_usd, notes, run_id),
    )
    conn.commit()
