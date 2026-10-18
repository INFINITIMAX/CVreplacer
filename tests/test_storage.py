"""Teste pentru src/cvreplacer/storage/.

Ordinea urmeaza prioritatea din docs/handoff/E2-tester.md:
1. first_seen nu se schimba niciodata
2. ciclul de viata activ -> mort -> reinviat
3. scores - cheia compusa
4. age_days
5. migrari
6. runs si applications

Fiecare test foloseste o baza temporara proprie (fixtura `conn` din conftest.py).
"""

from __future__ import annotations

import sqlite3

import pytest
from conftest import make_job

from cvreplacer.storage import (
    age_days,
    connect,
    finish_run,
    mark_absent,
    mark_applied,
    save_score,
    schema,
    start_run,
    upsert_seen,
)

URL = "https://exemplu.test/1"
URL_B = "https://exemplu.test/2"

T1 = "2026-01-01T00:00:00Z"
T2 = "2026-01-02T00:00:00Z"
T3 = "2026-01-03T00:00:00Z"
T4 = "2026-01-04T00:00:00Z"
T5 = "2026-01-05T00:00:00Z"
T6 = "2026-01-06T00:00:00Z"


def _first_seen(conn: sqlite3.Connection, url: str) -> str:
    row = conn.execute("SELECT first_seen FROM jobs WHERE url = ?", (url,)).fetchone()
    return row["first_seen"]


def _job_row(conn: sqlite3.Connection, url: str) -> sqlite3.Row:
    return conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()


# --------------------------------------------------------------------------
# 1. first_seen nu se schimba niciodata
# --------------------------------------------------------------------------


def test_new_job_sets_first_seen_equal_last_seen_equal_run_at(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    row = _job_row(conn, URL)
    assert row["first_seen"] == T1
    assert row["last_seen"] == T1


def test_seeing_job_again_later_keeps_first_seen_updates_last_seen(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    upsert_seen(conn, [make_job(URL)], run_at=T2)
    row = _job_row(conn, URL)
    assert row["first_seen"] == T1
    assert row["last_seen"] == T2


def test_seeing_job_five_times_first_seen_stays_the_original(conn):
    for run_at in (T1, T2, T3, T4, T5):
        upsert_seen(conn, [make_job(URL)], run_at=run_at)
    row = _job_row(conn, URL)
    assert row["first_seen"] == T1
    assert row["last_seen"] == T5


def test_job_that_dies_and_revives_keeps_original_first_seen(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    # absenta de doua ori consecutiv -> mort
    mark_absent(conn, seen_urls=set(), run_at=T2)
    mark_absent(conn, seen_urls=set(), run_at=T3)
    assert _job_row(conn, URL)["status"] == "dead"

    # reapare la o data ulterioara
    upsert_seen(conn, [make_job(URL)], run_at=T6)
    row = _job_row(conn, URL)
    assert row["status"] == "active"
    assert row["first_seen"] == T1, "first_seen trebuie sa ramana data initiala, nu reinvierea"
    assert row["last_seen"] == T6


# --------------------------------------------------------------------------
# 2. ciclul de viata: activ -> mort -> reinviat
# --------------------------------------------------------------------------


def test_absent_one_run_increments_missing_runs_stays_active(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_absent(conn, seen_urls=set(), run_at=T2)
    row = _job_row(conn, URL)
    assert row["missing_runs"] == 1
    assert row["status"] == "active"


def test_absent_two_consecutive_runs_marks_dead(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_absent(conn, seen_urls=set(), run_at=T2)
    mark_absent(conn, seen_urls=set(), run_at=T3)
    row = _job_row(conn, URL)
    assert row["status"] == "dead"
    assert row["missing_runs"] == 2


def test_revived_job_has_active_status_and_zero_missing_runs(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_absent(conn, seen_urls=set(), run_at=T2)
    mark_absent(conn, seen_urls=set(), run_at=T3)
    assert _job_row(conn, URL)["status"] == "dead"

    upsert_seen(conn, [make_job(URL)], run_at=T4)
    row = _job_row(conn, URL)
    assert row["status"] == "active"
    assert row["missing_runs"] == 0


def test_job_seen_again_resets_missing_runs_to_zero(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_absent(conn, seen_urls=set(), run_at=T2)
    assert _job_row(conn, URL)["missing_runs"] == 1

    upsert_seen(conn, [make_job(URL)], run_at=T3)
    assert _job_row(conn, URL)["missing_runs"] == 0


def test_mark_absent_returns_count_for_that_run_only_not_running_total(conn):
    upsert_seen(conn, [make_job(URL), make_job(URL_B)], run_at=T1)

    # prima absenta pentru amandoua: niciunul nu moare inca
    first = mark_absent(conn, seen_urls=set(), run_at=T2)
    assert first == 0

    # a doua absenta consecutiva: amandoua mor acum
    second = mark_absent(conn, seen_urls=set(), run_at=T3)
    assert second == 2

    # a treia rulare: deja morti, nu se mai numara din nou
    third = mark_absent(conn, seen_urls=set(), run_at=T4)
    assert third == 0


# --------------------------------------------------------------------------
# 3. scores - cheia compusa
# --------------------------------------------------------------------------


def _save_default_score(conn, url=URL, prompt_version="v1", fit=0.5, scored_at=T1):
    save_score(
        conn,
        url=url,
        prompt_version=prompt_version,
        fit=fit,
        vetoed=False,
        veto_reason=None,
        requirements_json='{"cerinta": true}',
        usage_json='{"tokens": 42}',
        scored_at=scored_at,
    )


def test_different_prompt_versions_both_exist_for_same_url(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    _save_default_score(conn, prompt_version="v1", fit=0.3)
    _save_default_score(conn, prompt_version="v2", fit=0.7)

    rows = conn.execute(
        "SELECT prompt_version, fit FROM scores WHERE url = ? ORDER BY prompt_version", (URL,)
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["prompt_version"] == "v1"
    assert rows[0]["fit"] == 0.3
    assert rows[1]["prompt_version"] == "v2"
    assert rows[1]["fit"] == 0.7


def test_same_url_and_prompt_version_saved_twice_updates_not_duplicates(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    _save_default_score(conn, prompt_version="v1", fit=0.3, scored_at=T1)
    _save_default_score(conn, prompt_version="v1", fit=0.9, scored_at=T2)

    rows = conn.execute("SELECT fit, scored_at FROM scores WHERE url = ?", (URL,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["fit"] == 0.9
    assert rows[0]["scored_at"] == T2


def test_requirements_and_usage_json_roundtrip_identically(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    req = '{"python": {"met": true, "evidence": "3 ani experienta"}}'
    usage = '{"input_tokens": 100, "output_tokens": 20}'
    save_score(
        conn,
        url=URL,
        prompt_version="v1",
        fit=0.8,
        vetoed=False,
        veto_reason=None,
        requirements_json=req,
        usage_json=usage,
        scored_at=T1,
    )
    row = conn.execute(
        "SELECT requirements_json, usage_json FROM scores WHERE url = ?", (URL,)
    ).fetchone()
    assert row["requirements_json"] == req
    assert row["usage_json"] == usage


def test_save_score_for_unknown_url_raises_integrity_error(conn):
    """foreign key scores.url -> jobs.url; PRAGMA foreign_keys e ON din connect()."""
    with pytest.raises(sqlite3.IntegrityError):
        _save_default_score(conn, url="https://exemplu.test/inexistent")


# --------------------------------------------------------------------------
# 4. age_days
# --------------------------------------------------------------------------


def test_age_days_computes_fractional_difference_correctly(conn):
    upsert_seen(conn, [make_job(URL)], run_at="2026-01-01T00:00:00Z")
    result = age_days(conn, URL, now="2026-01-02T12:00:00Z")
    assert result == pytest.approx(1.5)


def test_age_days_unknown_url_raises_clear_error(conn):
    with pytest.raises(KeyError):
        age_days(conn, "https://exemplu.test/nu-exista", now=T1)


# --------------------------------------------------------------------------
# 5. migrari
# --------------------------------------------------------------------------


def test_connect_on_new_db_creates_all_tables_and_schema_version(tmp_path):
    db_path = tmp_path / "nou.db"
    connection = connect(db_path)
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"jobs", "scores", "applications", "runs", "schema_version"} <= tables
        assert schema.current_version(connection) == 1
    finally:
        connection.close()


def test_connect_twice_does_not_duplicate_schema_version_row(tmp_path):
    db_path = tmp_path / "dublu.db"
    first = connect(db_path)
    first.close()
    second = connect(db_path)
    try:
        rows = second.execute("SELECT version FROM schema_version").fetchall()
        assert len(rows) == 1
        assert rows[0]["version"] == 1
    finally:
        second.close()


def test_data_survives_a_second_connect(tmp_path):
    db_path = tmp_path / "persistent.db"
    first = connect(db_path)
    upsert_seen(first, [make_job(URL)], run_at=T1)
    first.close()

    second = connect(db_path)
    try:
        row = second.execute("SELECT * FROM jobs WHERE url = ?", (URL,)).fetchone()
        assert row is not None
        assert row["first_seen"] == T1
    finally:
        second.close()


# --------------------------------------------------------------------------
# 6. runs si applications
# --------------------------------------------------------------------------


def test_start_run_returns_id_and_finish_run_writes_counters(conn):
    run_id = start_run(conn)
    assert isinstance(run_id, int)

    finish_run(conn, run_id, n_harvested=10, n_filtered=4, n_scored=2, cost_usd=0.05, notes="ok")

    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row["finished_at"] is not None
    assert row["n_harvested"] == 10
    assert row["n_filtered"] == 4
    assert row["n_scored"] == 2
    assert row["cost_usd"] == pytest.approx(0.05)
    assert row["notes"] == "ok"


def test_mark_applied_writes_and_is_readable(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_applied(conn, URL, note="am trimis CV-ul")

    row = conn.execute("SELECT * FROM applications WHERE url = ?", (URL,)).fetchone()
    assert row is not None
    assert row["note"] == "am trimis CV-ul"
    assert row["outcome"] == "pending"
    assert row["applied_at"] is not None


def test_mark_applied_twice_upserts_instead_of_duplicating(conn):
    upsert_seen(conn, [make_job(URL)], run_at=T1)
    mark_applied(conn, URL, note="prima nota")
    mark_applied(conn, URL, note="a doua nota")

    rows = conn.execute("SELECT note FROM applications WHERE url = ?", (URL,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["note"] == "a doua nota"


# --------------------------------------------------------------------------
# 7. E3F: text venit din sursa + mark_absent pe surse
# --------------------------------------------------------------------------


def test_upsert_new_job_with_raw_text_marks_fetch_status_source(conn):
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="descrierea completa")], run_at=T1)

    row = _job_row(conn, URL)
    assert row["raw_text"] == "descrierea completa"
    assert row["fetch_status"] == "source"
    assert row["fetched_at"] == T1


def test_upsert_new_job_without_raw_text_leaves_fetch_columns_null(conn):
    upsert_seen(conn, [make_job(URL, raw_text=None)], run_at=T1)

    row = _job_row(conn, URL)
    assert row["raw_text"] is None
    assert row["fetch_status"] is None
    assert row["fetched_at"] is None


def test_existing_job_seen_again_with_other_raw_text_keeps_text_and_status(conn):
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="versiunea 1")], run_at=T1)
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="versiunea 2")], run_at=T2)

    row = _job_row(conn, URL)
    assert row["raw_text"] == "versiunea 1"
    assert row["fetch_status"] == "source"
    assert row["fetched_at"] == T1
    assert row["first_seen"] == T1
    assert row["last_seen"] == T2


def test_existing_job_without_text_does_not_get_text_from_later_run(conn):
    # anunt intrat prin peviitor (fara text), regasit de freehire (cu text):
    # randul existent nu se atinge, textul ramane de adus de fetch
    upsert_seen(conn, [make_job(URL, source="peviitor")], run_at=T1)
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="text nou")], run_at=T2)

    row = _job_row(conn, URL)
    assert row["raw_text"] is None
    assert row["fetch_status"] is None
    assert row["source"] == "peviitor"


def test_dead_job_revived_with_raw_text_keeps_old_text_columns(conn):
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="vechi")], run_at=T1)
    mark_absent(conn, set(), run_at=T2)
    mark_absent(conn, set(), run_at=T3)
    upsert_seen(conn, [make_job(URL, source="freehire", raw_text="nou")], run_at=T4)

    row = _job_row(conn, URL)
    assert row["status"] == "active"
    assert row["raw_text"] == "vechi"
    assert row["fetched_at"] == T1


def test_mark_absent_with_sources_ignores_other_sources_even_after_two_runs(conn):
    upsert_seen(
        conn,
        [make_job(URL, source="freehire"), make_job(URL_B, source="peviitor")],
        run_at=T1,
    )

    dead_1 = mark_absent(conn, set(), run_at=T2, sources={"freehire"})
    assert dead_1 == 0
    assert _job_row(conn, URL)["missing_runs"] == 1
    assert _job_row(conn, URL_B)["missing_runs"] == 0

    dead_2 = mark_absent(conn, set(), run_at=T3, sources={"freehire"})
    assert dead_2 == 1
    assert _job_row(conn, URL)["status"] == "dead"
    assert _job_row(conn, URL_B)["status"] == "active"
    assert _job_row(conn, URL_B)["missing_runs"] == 0


def test_mark_absent_with_sources_still_spares_seen_urls_of_that_source(conn):
    upsert_seen(
        conn,
        [make_job(URL, source="freehire"), make_job(URL_B, source="freehire")],
        run_at=T1,
    )

    mark_absent(conn, {URL}, run_at=T2, sources={"freehire"})

    assert _job_row(conn, URL)["missing_runs"] == 0
    assert _job_row(conn, URL_B)["missing_runs"] == 1


def test_mark_absent_with_empty_sources_touches_nothing(conn):
    upsert_seen(conn, [make_job(URL, source="freehire")], run_at=T1)

    mark_absent(conn, set(), run_at=T2, sources=set())
    mark_absent(conn, set(), run_at=T3, sources=set())

    row = _job_row(conn, URL)
    assert row["missing_runs"] == 0
    assert row["status"] == "active"


def test_mark_absent_without_sources_covers_all_sources(conn):
    upsert_seen(
        conn,
        [make_job(URL, source="freehire"), make_job(URL_B, source="peviitor")],
        run_at=T1,
    )

    mark_absent(conn, set(), run_at=T2)
    dead = mark_absent(conn, set(), run_at=T3)

    assert dead == 2
    assert _job_row(conn, URL)["status"] == "dead"
    assert _job_row(conn, URL_B)["status"] == "dead"
