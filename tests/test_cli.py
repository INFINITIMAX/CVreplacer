"""Teste pentru cvreplacer.cli (E3F): _needs_download si cmd_harvest.

cmd_harvest ruleaza cu baza SQLite temporara; sursele sunt inlocuite cu rezultate fabricate
(nicio cerere de retea). Profilul si interogarile sunt inlocuite ca sa nu depinda de
data/cv/profile.json.
"""

from __future__ import annotations

import pytest
from conftest import make_job, make_job_row

from cvreplacer import cli
from cvreplacer.sources.peviitor import HarvestResult
from cvreplacer.storage import connect, upsert_seen

T0 = "2026-01-01T00:00:00Z"

URL_P = "https://exemplu.test/peviitor/1"
URL_F = "https://exemplu.test/freehire/1"

# --------------------------------------------------------------------------
# _needs_download
# --------------------------------------------------------------------------


def test_job_with_text_from_source_does_not_need_download():
    assert cli._needs_download(make_job_row(fetch_status="source")) is False


@pytest.mark.parametrize("status", [None, "ok", "403"])
def test_other_fetch_statuses_need_download(status):
    assert cli._needs_download(make_job_row(fetch_status=status)) is True


# --------------------------------------------------------------------------
# cmd_harvest
# --------------------------------------------------------------------------


@pytest.fixture
def harvest_env(tmp_path, monkeypatch):
    """Mediu izolat: baza temporara, variabile de mediu inventate, profil fals."""
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("CVR_DB_PATH", str(db_path))
    monkeypatch.setenv("CVR_PEVIITOR_BASE", "https://peviitor.exemplu.test")
    monkeypatch.setenv("CVR_FREEHIRE_BASE", "https://freehire.exemplu.test")
    monkeypatch.setenv("CVR_USER_AGENT", "test-agent")
    monkeypatch.setattr(cli.queries, "load_profile", lambda path: {})
    monkeypatch.setattr(cli.queries, "build_queries", lambda profile: ["q1", "q2"])

    seed = connect(db_path)
    upsert_seen(
        seed,
        [
            make_job(URL_P, source="peviitor"),
            make_job(URL_F, source="freehire", raw_text="text"),
        ],
        run_at=T0,
    )
    seed.close()
    return db_path


def _patch_sources(monkeypatch, peviitor: HarvestResult, freehire: HarvestResult) -> None:
    monkeypatch.setattr(cli.peviitor, "harvest", lambda terms, **kw: peviitor)
    monkeypatch.setattr(cli.freehire, "harvest", lambda terms, **kw: freehire)


def _row(db_path, url):
    conn = connect(db_path)
    try:
        return conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
    finally:
        conn.close()


def test_fully_failed_freehire_does_not_age_its_existing_jobs(harvest_env, monkeypatch):
    peviitor_ok = HarvestResult(
        n_queries=2, n_raw=1, n_unique=1, n_failed=0, jobs=[make_job(URL_P, source="peviitor")]
    )
    freehire_down = HarvestResult(n_queries=2, n_raw=0, n_unique=0, n_failed=2, jobs=[])
    _patch_sources(monkeypatch, peviitor_ok, freehire_down)

    cli.main(["harvest"])
    cli.main(["harvest"])  # a doua rulare: altfel ar fi ajuns 'dead'

    freehire_row = _row(harvest_env, URL_F)
    assert freehire_row["missing_runs"] == 0
    assert freehire_row["status"] == "active"


def test_partially_failed_freehire_still_ages_absent_jobs(harvest_env, monkeypatch):
    # contrapartida: 1 din 2 interogari esuate NU e "sursa cazuta", deci absenta conteaza
    peviitor_ok = HarvestResult(
        n_queries=2, n_raw=1, n_unique=1, n_failed=0, jobs=[make_job(URL_P, source="peviitor")]
    )
    freehire_partial = HarvestResult(n_queries=2, n_raw=0, n_unique=0, n_failed=1, jobs=[])
    _patch_sources(monkeypatch, peviitor_ok, freehire_partial)

    cli.main(["harvest"])

    assert _row(harvest_env, URL_F)["missing_runs"] == 1


def test_fully_failed_peviitor_does_not_age_peviitor_jobs_but_freehire_still_runs(
    harvest_env, monkeypatch
):
    peviitor_down = HarvestResult(n_queries=2, n_raw=0, n_unique=0, n_failed=2, jobs=[])
    freehire_ok = HarvestResult(
        n_queries=2, n_raw=0, n_unique=0, n_failed=0, jobs=[]
    )  # URL_F absent din rularea ok
    _patch_sources(monkeypatch, peviitor_down, freehire_ok)

    cli.main(["harvest"])

    assert _row(harvest_env, URL_P)["missing_runs"] == 0
    assert _row(harvest_env, URL_F)["missing_runs"] == 1


def test_source_peviitor_only_does_not_age_freehire_jobs(harvest_env, monkeypatch):
    peviitor_ok = HarvestResult(n_queries=2, n_raw=0, n_unique=0, n_failed=0, jobs=[])

    def boom(terms, **kw):
        raise AssertionError("freehire nu trebuie apelat cu --source peviitor")

    monkeypatch.setattr(cli.peviitor, "harvest", lambda terms, **kw: peviitor_ok)
    monkeypatch.setattr(cli.freehire, "harvest", boom)

    cli.main(["harvest", "--source", "peviitor"])

    assert _row(harvest_env, URL_P)["missing_runs"] == 1
    assert _row(harvest_env, URL_F)["missing_runs"] == 0


def test_same_url_from_both_sources_is_stored_once_first_source_wins(harvest_env, monkeypatch):
    shared = "https://exemplu.test/comun"
    peviitor_res = HarvestResult(
        n_queries=2,
        n_raw=1,
        n_unique=1,
        n_failed=0,
        jobs=[make_job(shared, source="peviitor")],
    )
    freehire_res = HarvestResult(
        n_queries=2,
        n_raw=1,
        n_unique=1,
        n_failed=0,
        jobs=[make_job(shared, source="freehire", raw_text="text")],
    )
    _patch_sources(monkeypatch, peviitor_res, freehire_res)

    cli.main(["harvest"])

    conn = connect(harvest_env)
    try:
        rows = conn.execute("SELECT source FROM jobs WHERE url = ?", (shared,)).fetchall()
    finally:
        conn.close()
    assert [r["source"] for r in rows] == ["peviitor"]
