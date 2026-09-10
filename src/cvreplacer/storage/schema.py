"""DDL si migrari versionate pentru baza SQLite.

Fara ORM. Migrarile sunt scripturi SQL simple, aplicate in ordine,
o singura data, tinute evidenta in tabela schema_version.
"""

from __future__ import annotations

import sqlite3

# migrarea 1: schema initiala - jobs, scores, applications, runs
_MIGRATION_1 = """
CREATE TABLE jobs (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    city TEXT,
    remote TEXT,
    source TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    missing_runs INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    fetch_status TEXT,
    raw_text TEXT,
    fetched_at TEXT
);

CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL REFERENCES jobs(url),
    prompt_version TEXT NOT NULL,
    fit REAL NOT NULL,
    vetoed INTEGER NOT NULL,
    veto_reason TEXT,
    requirements_json TEXT NOT NULL,
    usage_json TEXT,
    scored_at TEXT NOT NULL,
    UNIQUE (url, prompt_version)
);

CREATE TABLE applications (
    url TEXT PRIMARY KEY REFERENCES jobs(url),
    applied_at TEXT NOT NULL,
    note TEXT,
    outcome TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    n_harvested INTEGER,
    n_filtered INTEGER,
    n_scored INTEGER,
    cost_usd REAL,
    notes TEXT
);
"""

# versiune -> script SQL. adaugi o migrare noua doar prin a adauga o cheie noua,
# niciodata prin a edita una existenta.
MIGRATIONS: dict[int, str] = {
    1: _MIGRATION_1,
}


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (0)")
        conn.commit()


def current_version(conn: sqlite3.Connection) -> int:
    """Versiunea de schema aplicata pana acum. 0 pentru o baza noua."""
    _ensure_version_table(conn)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return row[0]


def migrate(conn: sqlite3.Connection) -> None:
    """Aplica in ordine migrarile lipsa fata de versiunea curenta."""
    version = current_version(conn)
    for target in sorted(MIGRATIONS):
        if target <= version:
            continue
        conn.executescript(MIGRATIONS[target])
        conn.execute("UPDATE schema_version SET version = ?", (target,))
        conn.commit()
