"""API-ul public al modulului fetch: descarcarea descrierilor de anunt.

Orchestreaza client.py (retea + ritm per domeniu), cache.py (disc) si
extract.py (text principal), in paralel, dar niciodata doua cereri
simultane catre acelasi domeniu (spec.md R7, brief E5).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from cvreplacer.config import FetchConfig
from cvreplacer.fetch.cache import DiskCache, is_fresh
from cvreplacer.fetch.client import DomainRateLimiter, FetchClient, build_http_client
from cvreplacer.fetch.extract import extract_text, is_too_short

# Valorile posibile pentru fetch_status (brief E5).
FETCH_STATUSES = ("ok", "403", "404", "timeout", "too_short", "error")

__all__ = ["FETCH_STATUSES", "FetchResult", "fetch_many"]


@dataclass(frozen=True)
class FetchResult:
    """Rezultatul descarcarii + extragerii pentru un singur URL.

    Corespunde campurilor pe care storage ar trebui sa le scrie pe jobs:
    raw_text, fetch_status, fetched_at (vezi raportul E5 pentru gapul de
    persistenta - storage nu expune inca operatia de actualizare).
    """

    url: str
    raw_text: str | None
    fetch_status: str
    fetched_at: str
    from_cache: bool


def fetch_many(
    urls: Sequence[str],
    config: FetchConfig,
    *,
    force: bool = False,
    http_client: httpx.Client | None = None,
    clock=time.monotonic,
    sleep=time.sleep,
    now: datetime | None = None,
) -> list[FetchResult]:
    """Descarca si extrage textul pentru fiecare url, in paralel.

    force=True ignora cache-ul (redescarca tot, chiar daca e proaspat).
    http_client, clock, sleep si now sunt injectabile - testele nu ating
    reteaua reala si nu asteapta timp real (regula din brief E5).
    """
    owns_client = http_client is None
    client = http_client or build_http_client(config.user_agent, config.timeout_s)
    cache = DiskCache(config.cache_dir)
    rate_limiter = DomainRateLimiter(config.rate_limit_s, clock=clock, sleep=sleep)
    fetch_client = FetchClient(client, config.user_agent, config.timeout_s, rate_limiter, sleep=sleep)
    moment = now or datetime.now(UTC)

    def _one(url: str) -> FetchResult:
        return _fetch_one(url, config, cache, fetch_client, force=force, now=moment)

    try:
        # Concurenta globala limitata la CVR_FETCH_CONCURRENCY; concurenta
        # per domeniu e limitata separat, la 1, de DomainRateLimiter.gate().
        with ThreadPoolExecutor(max_workers=max(1, config.concurrency)) as pool:
            results = list(pool.map(_one, urls))
    finally:
        if owns_client:
            client.close()
    return results


def _fetch_one(
    url: str,
    config: FetchConfig,
    cache: DiskCache,
    fetch_client: FetchClient,
    *,
    force: bool,
    now: datetime,
) -> FetchResult:
    if not force:
        entry = cache.read(url)
        if entry is not None and is_fresh(entry, config.cache_ttl_days, now):
            return _from_html(url, entry.html, entry.fetched_at, config, from_cache=True)

    outcome = fetch_client.fetch(url)
    if outcome.status == "ok" and outcome.html is not None:
        cache.write(url, outcome.html, outcome.fetched_at)
        return _from_html(url, outcome.html, outcome.fetched_at, config, from_cache=False)

    return FetchResult(
        url=url,
        raw_text=None,
        fetch_status=outcome.status,
        fetched_at=outcome.fetched_at,
        from_cache=False,
    )


def _from_html(
    url: str, html: str, fetched_at: str, config: FetchConfig, *, from_cache: bool
) -> FetchResult:
    text = extract_text(html, config.max_description_chars)
    if is_too_short(text):
        # Sub 200 de caractere - probabil pagina e randata din JavaScript,
        # tratam ca esec de extragere, nu ca succes cu text sarac (brief E5).
        return FetchResult(
            url=url, raw_text=None, fetch_status="too_short", fetched_at=fetched_at,
            from_cache=from_cache,
        )
    return FetchResult(
        url=url, raw_text=text, fetch_status="ok", fetched_at=fetched_at, from_cache=from_cache
    )
