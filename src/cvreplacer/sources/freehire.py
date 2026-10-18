"""Clientul freehire.me.

Reguli din brief, verificate live pe 18-10-2026:
- API-ul documentat, fara autentificare: GET /api/v1/agent/jobs/search.
- `limit` are plafon 100 pe server; paginarea prin `offset` functioneaza.
- `countries` e cod ISO (ro); "Romania" intoarce 0 rezultate.
- Descrierea completa vine in raspunsul de cautare, deci anunturile freehire
  nu mai trec prin fetch.
- Un 4xx e un raspuns, nu o eroare de retea: nu se reincearca (CLAUDE.md #5).
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import httpx

from cvreplacer.sources.base import raw_job_from_freehire_doc
from cvreplacer.sources.peviitor import HarvestResult
from cvreplacer.storage.models import RawJob

_TIMEOUT_S = 20.0
_PAGE_SIZE = 100
_SEARCH_PATH = "/api/v1/agent/jobs/search"


def search(
    term: str,
    *,
    client: httpx.Client,
    country: str,
    posted_within_days: int,
    max_pages: int,
    max_chars: int,
    rate_limit_s: float = 0.0,
) -> list[RawJob]:
    """O interogare paginata. Fiecare pagina se reincearca o data, la erori de retea sau 5xx."""
    jobs: list[RawJob] = []
    offset = 0
    for page in range(max_pages):
        if page > 0:
            time.sleep(rate_limit_s)

        payload = _get_page_with_retry(
            client,
            {
                "q": term,
                "countries": country,
                "posted_within_days": posted_within_days,
                "limit": _PAGE_SIZE,
                "offset": offset,
            },
        )
        docs = payload.get("data", [])
        for doc in docs:
            job = raw_job_from_freehire_doc(doc, max_chars)
            if job is not None:
                jobs.append(job)

        offset += _PAGE_SIZE
        total = payload.get("meta", {}).get("total")
        if len(docs) < _PAGE_SIZE or (isinstance(total, int) and offset >= total):
            break
    return jobs


def harvest(
    terms: Iterable[str],
    *,
    rate_limit_s: float,
    base_url: str | None = None,
    user_agent: str | None = None,
    country: str,
    posted_within_days: int,
    max_pages: int,
    max_chars: int,
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
                jobs = search(
                    term,
                    client=client,
                    country=country,
                    posted_within_days=posted_within_days,
                    max_pages=max_pages,
                    max_chars=max_chars,
                    rate_limit_s=rate_limit_s,
                )
            # ValueError: un 200 care nu e JSON (pagina de mentenanta) sau JSON
            # de forma neasteptata - interogarea esueaza, rularea continua.
            except (httpx.HTTPError, ValueError):
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


def _get_page_with_retry(client: httpx.Client, params: dict) -> dict:
    """O singura reincercare, doar la eroare de retea sau 5xx. Un 4xx se propaga direct."""
    try:
        return _get_page(client, params)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code < 500:
            raise
        return _get_page(client, params)
    except httpx.HTTPError:
        return _get_page(client, params)


def _get_page(client: httpx.Client, params: dict) -> dict:
    response = client.get(_SEARCH_PATH, params=params)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        # eroare de protocol, nu de tip: aceeasi clasa ca JSONDecodeError, prinsa in harvest
        raise ValueError("raspuns freehire neasteptat: nu e obiect JSON")  # noqa: TRY004
    return payload
