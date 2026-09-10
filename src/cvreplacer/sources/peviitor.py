"""Clientul peViitor.

Reguli din brief, verificate live pe 10-09-2026:
- `start` e ignorat de API, nu se pagineaza; acoperirea vine din numarul de
  interogari, nu din parcurgerea indexului.
- `rows` functioneaza si poate cere multe rezultate intr-o singura cerere.
- `date` e momentul indexarii, nu al publicarii - se ignora complet aici,
  prospetimea vine din storage.first_seen.
- `q` e un singur termen liber, fara sintaxa pe campuri si fara AND real.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx

from cvreplacer.sources.base import raw_job_from_peviitor_doc
from cvreplacer.storage.models import RawJob

_TIMEOUT_S = 15.0
_DEFAULT_ROWS = 200


@dataclass(frozen=True)
class HarvestResult:
    """Rezumatul unei recoltari peste mai multe interogari."""

    n_queries: int
    n_raw: int
    n_unique: int
    n_failed: int
    jobs: list[RawJob] = field(default_factory=list)


def search(term: str, rows: int = _DEFAULT_ROWS, *, client: httpx.Client) -> list[RawJob]:
    """O singura interogare. Nu reincearca - reincercarea e treaba lui harvest()."""
    response = client.get("/search/", params={"q": term, "rows": rows})

    # Zero rezultate nu e o eroare, dar API-ul le raporteaza ca 404 cu
    # {"error": "No jobs found"}. Verificat live pe 10-09-2026: q=pgvector -> 404,
    # q=Python -> 200. Daca lasam raise_for_status() sa arunce, un termen care
    # pur si simplu nu are anunturi in Romania apare ca interogare esuata - ceea
    # ce umfla n_failed si mascheaza esecurile adevarate.
    if response.status_code == httpx.codes.NOT_FOUND:
        return []

    response.raise_for_status()
    payload = response.json()
    docs = payload.get("response", {}).get("docs", [])

    jobs: list[RawJob] = []
    for doc in docs:
        job = raw_job_from_peviitor_doc(doc)
        if job is not None:
            jobs.append(job)
    return jobs


def harvest(
    terms: Iterable[str],
    *,
    rate_limit_s: float,
    base_url: str | None = None,
    user_agent: str | None = None,
    rows: int = _DEFAULT_ROWS,
    client: httpx.Client | None = None,
) -> HarvestResult:
    """Recolteaza peste toate interogarile, unificand rezultatele pe url.

    Daca `client` nu e dat, se construieste unul din base_url/user_agent
    (folosit de cli.py). Testele injecteaza propriul client fals.
    """
    owns_client = client is None
    if owns_client:
        if not base_url or not user_agent:
            raise ValueError("base_url si user_agent sunt obligatorii cand nu se da un client")
        client = httpx.Client(
            base_url=base_url,
            headers={"User-Agent": user_agent},
            timeout=_TIMEOUT_S,
        )

    try:
        term_list = [t for t in terms if t]
        seen_urls: set[str] = set()
        unique_jobs: list[RawJob] = []
        n_raw = 0
        n_failed = 0

        for index, term in enumerate(term_list):
            try:
                jobs = _search_with_retry(term, rows, client=client)
            except httpx.HTTPError:
                n_failed += 1
                jobs = []

            n_raw += len(jobs)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    unique_jobs.append(job)

            if index < len(term_list) - 1:
                time.sleep(rate_limit_s)

        return HarvestResult(
            n_queries=len(term_list),
            n_raw=n_raw,
            n_unique=len(unique_jobs),
            n_failed=n_failed,
            jobs=unique_jobs,
        )
    finally:
        if owns_client:
            client.close()


def _search_with_retry(term: str, rows: int, *, client: httpx.Client) -> list[RawJob]:
    """O singura reincercare la eroare de retea, apoi renuntare."""
    try:
        return search(term, rows, client=client)
    except httpx.HTTPError:
        return search(term, rows, client=client)
