"""Cache pe disc pentru HTML descarcat.

Un fisier JSON per URL, in CVR_CACHE_DIR, numit dupa hash-ul URL-ului.
Cache-ul e sub data/, deja ignorat de git (CLAUDE.md regula #4) - nu se muta.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CacheEntry:
    """O intrare de cache: HTML-ul brut plus momentul descarcarii."""

    url: str
    html: str
    fetched_at: str  # ISO 8601 UTC, format identic cu restul proiectului


def cache_key(url: str) -> str:
    """Hash stabil al URL-ului, folosit ca nume de fisier - url-urile pot
    contine caractere nepermise intr-un nume de fisier (?, &, :).
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class DiskCache:
    """Citire/scriere pe disc, un fisier JSON per URL."""

    def __init__(self, cache_dir: str | Path) -> None:
        self._dir = Path(cache_dir)

    def read(self, url: str) -> CacheEntry | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Cache corupt sau ilizibil: tratat ca lipsa, nu ca eroare fatala -
            # url-ul se redescarca, mai sigur decat sa opreasca toata rularea.
            return None
        return CacheEntry(url=data["url"], html=data["html"], fetched_at=data["fetched_at"])

    def write(self, url: str, html: str, fetched_at: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(url)
        path.write_text(
            json.dumps({"url": url, "html": html, "fetched_at": fetched_at}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _path(self, url: str) -> Path:
        return self._dir / f"{cache_key(url)}.json"


def is_fresh(entry: CacheEntry, ttl_days: int, now: datetime) -> bool:
    """True daca entry e mai noua decat ttl_days fata de now (injectabil pt teste)."""
    fetched_at = datetime.fromisoformat(entry.fetched_at)
    age_seconds = (now - fetched_at).total_seconds()
    return age_seconds < ttl_days * 86400
