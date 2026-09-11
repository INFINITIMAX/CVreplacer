"""Teste pentru filters.dedup — acelasi job, anunturi diferite (republicari)."""

from __future__ import annotations

from conftest import make_job_row

from cvreplacer.filters.dedup import make_dedup_filter


def _apply(jobs):
    step = make_dedup_filter()
    return step.fn(jobs)


def test_same_title_and_company_keeps_the_oldest_first_seen():
    older = make_job_row(
        url="https://exemplu.test/vechi",
        title="Python Developer",
        company="Exemplu SRL",
        first_seen="2026-01-01T00:00:00Z",
    )
    newer = make_job_row(
        url="https://exemplu.test/nou",
        title="Python Developer",
        company="Exemplu SRL",
        first_seen="2026-01-10T00:00:00Z",
    )
    kept = _apply([newer, older])
    assert len(kept) == 1
    assert kept[0].url == "https://exemplu.test/vechi"


def test_reference_codes_in_title_are_ignored_for_comparison():
    job_a = make_job_row(
        url="https://exemplu.test/a",
        title="Senior Python Developer IRC300958",
        company="Agentie SRL",
        first_seen="2026-01-01T00:00:00Z",
    )
    job_b = make_job_row(
        url="https://exemplu.test/b",
        title="Senior Python Developer IRC304030",
        company="Agentie SRL",
        first_seen="2026-01-05T00:00:00Z",
    )
    kept = _apply([job_a, job_b])
    assert len(kept) == 1
    assert kept[0].url == "https://exemplu.test/a"


def test_diacritics_and_punctuation_ignored_in_comparison():
    job_a = make_job_row(
        url="https://exemplu.test/a",
        title="Dezvoltator Python!",
        company="Compania Exemplu SRL.",
        first_seen="2026-01-01T00:00:00Z",
    )
    job_b = make_job_row(
        url="https://exemplu.test/b",
        title="Dezvoltator Pythön",
        company="Compania Exemplu SRL",
        first_seen="2026-01-02T00:00:00Z",
    )
    kept = _apply([job_a, job_b])
    assert len(kept) == 1
    assert kept[0].url == "https://exemplu.test/a"


def test_different_companies_same_title_are_not_duplicates():
    job_a = make_job_row(
        url="https://exemplu.test/a",
        title="Python Developer",
        company="Compania A SRL",
        first_seen="2026-01-01T00:00:00Z",
    )
    job_b = make_job_row(
        url="https://exemplu.test/b",
        title="Python Developer",
        company="Compania B SRL",
        first_seen="2026-01-01T00:00:00Z",
    )
    kept = _apply([job_a, job_b])
    assert {job.url for job in kept} == {"https://exemplu.test/a", "https://exemplu.test/b"}


def test_no_duplicates_keeps_all_jobs_unchanged():
    job_a = make_job_row(url="https://exemplu.test/a", title="Python Developer")
    job_b = make_job_row(url="https://exemplu.test/b", title="Java Developer")
    kept = _apply([job_a, job_b])
    assert len(kept) == 2
