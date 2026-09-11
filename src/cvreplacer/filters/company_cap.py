"""Filtrul 'company_cap': plafon per companie.

CVR_MAX_PER_COMPANY. Trei agentii de personal fac 21% din index si posteaza
zeci de anunturi aproape identice - fara plafon, ocupa tot clasamentul.

Cand se depaseste plafonul, se pastreaza cele mai recente dupa first_seen -
sunt cele la care mai poti aplica.
"""

from __future__ import annotations

from collections.abc import Sequence

from cvreplacer.config import CompanyCapConfig
from cvreplacer.filters import FilterStep
from cvreplacer.filters.dedup import normalize_company
from cvreplacer.storage.models import JobRow


def make_company_cap_filter(config: CompanyCapConfig) -> FilterStep:
    def _apply(jobs: Sequence[JobRow]) -> list[JobRow]:
        by_company: dict[str, list[JobRow]] = {}
        for job in jobs:
            key = normalize_company(job.company)
            by_company.setdefault(key, []).append(job)

        kept: list[JobRow] = []
        for company_jobs in by_company.values():
            company_jobs.sort(key=lambda job: job.first_seen, reverse=True)
            kept.extend(company_jobs[: config.max_per_company])

        kept_urls = {job.url for job in kept}
        return [job for job in jobs if job.url in kept_urls]

    return FilterStep(name="company_cap", fn=_apply)
