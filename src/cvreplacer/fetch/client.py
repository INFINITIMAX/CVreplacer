"""Descarcarea, politicoasa, cu ritm per domeniu (spec.md R7, CLAUDE.md regula #5).

User-Agent cu contact, timeout explicit, o singura reincercare doar la
eroare de retea sau 5xx (niciodata la 403/404 - alea sunt raspunsuri, nu
accidente), respecta Retry-After, redirecturi limitate.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

# Redirecturi urmarite inainte sa renuntam - suficient pentru lanturi normale
# (ex. shortlink catre pagina finala), fara sa intram in bucle.
_MAX_REDIRECTS = 5


def build_http_client(user_agent: str, timeout_s: float) -> httpx.Client:
    """Clientul implicit, folosit cand apelantul nu injecteaza unul (productie).

    user_agent si timeout_s nu se seteaza aici pe client, ci per cerere in
    FetchClient - httpx accepta ambele la nivel de client si de cerere, dar
    tinerea lor in FetchClient pastreaza un singur loc de adevar pentru politete.
    """
    del user_agent, timeout_s
    return httpx.Client(max_redirects=_MAX_REDIRECTS)


class DomainRateLimiter:
    """Ritm minim intre doua cereri catre acelasi domeniu, plus serializare:
    niciodata doua cereri simultane catre acelasi domeniu.

    Domenii diferite nu se asteapta unul pe altul - cheia e domeniul, nu un
    lacat global (212 domenii distincte; o pauza globala ar dura ~7 minute
    degeaba cand fiecare domeniu e lovit o data sau de doua ori, brief E5).
    """

    def __init__(
        self,
        min_interval_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last_access: dict[str, float] = {}
        self._domain_locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def _lock_for(self, domain: str) -> threading.Lock:
        with self._registry_lock:
            lock = self._domain_locks.get(domain)
            if lock is None:
                lock = threading.Lock()
                self._domain_locks[domain] = lock
            return lock

    @contextmanager
    def gate(self, domain: str):
        """Blocheaza pana cand domeniul e liber si ritmul minim a trecut de la
        ultimul acces catre acelasi domeniu. Alte domenii nu sunt afectate.
        """
        lock = self._lock_for(domain)
        lock.acquire()
        try:
            last = self._last_access.get(domain)
            if last is not None:
                wait = self._min_interval_s - (self._clock() - last)
                if wait > 0:
                    self._sleep(wait)
            yield
        finally:
            self._last_access[domain] = self._clock()
            lock.release()


@dataclass(frozen=True)
class FetchOutcome:
    """Rezultatul unei cereri de retea, inainte de extragerea textului."""

    url: str
    html: str | None
    status: str  # ok | 403 | 404 | timeout | error
    fetched_at: str


class FetchClient:
    """Descarca un URL: politete (UA, timeout, o reincercare, Retry-After),
    serializat/ritmat pe domeniu prin DomainRateLimiter injectat.
    """

    def __init__(
        self,
        http_client: httpx.Client,
        user_agent: str,
        timeout_s: float,
        rate_limiter: DomainRateLimiter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http_client
        self._headers = {"User-Agent": user_agent}
        self._timeout_s = timeout_s
        self._rate_limiter = rate_limiter
        self._sleep = sleep

    def fetch(self, url: str) -> FetchOutcome:
        domain = urlparse(url).netloc
        with self._rate_limiter.gate(domain):
            resp, err = self._attempt(url)
            if self._should_retry(resp, err):
                retry_after = _retry_after_seconds(resp)
                if retry_after:
                    self._sleep(retry_after)
                resp, err = self._attempt(url)
        status, html = self._classify(resp, err)
        return FetchOutcome(url=url, html=html, status=status, fetched_at=_now_iso())

    def _attempt(self, url: str) -> tuple[httpx.Response | None, str | None]:
        try:
            resp = self._http.get(
                url, headers=self._headers, timeout=self._timeout_s, follow_redirects=True
            )
        except httpx.TimeoutException:
            return None, "timeout"
        except httpx.HTTPError:
            # Eroare de retea (DNS, conexiune refuzata etc.) - nu e un raspuns HTTP.
            return None, "error"
        return resp, None

    @staticmethod
    def _should_retry(resp: httpx.Response | None, err: str | None) -> bool:
        # O singura reincercare, doar la eroare de retea sau 5xx - niciodata
        # la 403/404, alea sunt raspunsuri valide, nu accidente (brief E5).
        if err in ("timeout", "error"):
            return True
        return resp is not None and 500 <= resp.status_code < 600

    @staticmethod
    def _classify(resp: httpx.Response | None, err: str | None) -> tuple[str, str | None]:
        if err is not None:
            return err, None
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code == 404:
            return "404", None
        if resp.status_code == 403:
            return "403", None
        return "error", None


def _retry_after_seconds(resp: httpx.Response | None) -> float | None:
    if resp is None:
        return None
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        # Formatul HTTP-date pentru Retry-After nu e tratat - destul de rar
        # incat sa nu justifice complexitatea unui parser de date aici.
        return None


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
