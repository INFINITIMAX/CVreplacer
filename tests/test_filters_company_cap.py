"""Teste pentru filters.company_cap — plafon per companie."""

from __future__ import annotations

from conftest import make_job_row

from cvreplacer.config import CompanyCapConfig
from cvreplacer.filters.company_cap import make_company_cap_filter


def _apply(jobs, max_per_company=3):
    step = make_company_cap_filter(CompanyCapConfig(max_per_company=max_per_company))
    return step.fn(jobs)


def test_over_cap_keeps_the_most_recent_by_first_seen():
    jobs = [
        make_job_row(url=f"https://exemplu.test/{i}", first_seen=f"2026-01-0{i}T00:00:00Z")
        for i in range(1, 6)
    ]
    kept = _apply(jobs, max_per_company=3)
    kept_urls = {job.url for job in kept}
    assert kept_urls == {
        "https://exemplu.test/3",
        "https://exemplu.test/4",
        "https://exemplu.test/5",
    }


def test_under_cap_nothing_is_cut():
    jobs = [
        make_job_row(url="https://exemplu.test/1", first_seen="2026-01-01T00:00:00Z"),
        make_job_row(url="https://exemplu.test/2", first_seen="2026-01-02T00:00:00Z"),
    ]
    kept = _apply(jobs, max_per_company=3)
    assert len(kept) == 2


def test_cap_applies_per_company_not_globally():
    company_a = [
        make_job_row(
            url=f"https://exemplu.test/a{i}",
            company="Compania A SRL",
            first_seen=f"2026-01-0{i}T00:00:00Z",
        )
        for i in range(1, 5)
    ]
    company_b = [
        make_job_row(
            url=f"https://exemplu.test/b{i}",
            company="Compania B SRL",
            first_seen=f"2026-01-0{i}T00:00:00Z",
        )
        for i in range(1, 5)
    ]
    kept = _apply(company_a + company_b, max_per_company=3)
    kept_companies = {job.company for job in kept}
    assert kept_companies == {"Compania A SRL", "Compania B SRL"}
    assert len(kept) == 6, "3 pastrate per companie, nu 3 in total"


def test_company_name_normalization_groups_same_company():
    jobs = [
        make_job_row(
            url="https://exemplu.test/1", company="Exemplu SRL", first_seen="2026-01-01T00:00:00Z"
        ),
        make_job_row(
            url="https://exemplu.test/2",
            company="EXEMPLU SRL.",
            first_seen="2026-01-02T00:00:00Z",
        ),
        make_job_row(
            url="https://exemplu.test/3", company="Exemplu SRL", first_seen="2026-01-03T00:00:00Z"
        ),
    ]
    kept = _apply(jobs, max_per_company=2)
    assert len(kept) == 2
    kept_urls = {job.url for job in kept}
    assert kept_urls == {"https://exemplu.test/2", "https://exemplu.test/3"}
