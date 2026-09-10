"""Normalizarea campurilor brute de la surse, comuna tuturor surselor.

Fiecare sursa produce RawJob (definit in storage.models) prin functiile
de aici, ca formatul sa fie identic indiferent de unde vine anuntul.
"""

from __future__ import annotations

import html
import re

from cvreplacer.storage.models import RawJob

_ROMANIA_SUFFIX = ", Romania"

_REMOTE_MAP = {
    "remote": "remote",
    "hybrid": "hybrid",
    "hibrid": "hybrid",
    "on-site": "on-site",
    "onsite": "on-site",
    "on site": "on-site",
    "la birou": "on-site",
    "la sediu": "on-site",
}


def normalize_text(value: str | None) -> str:
    """Strip, colapsare spatii multiple, decodare entitati HTML (&amp; apare in date)."""
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_city(cities: list[str] | None) -> str | None:
    """Ia primul oras din lista; 'Romania' singur sau lista goala -> None."""
    if not cities:
        return None
    first = cities[0]
    if not isinstance(first, str):
        return None
    first = first.strip()
    if not first or first == "Romania":
        return None
    if first.endswith(_ROMANIA_SUFFIX):
        first = first[: -len(_ROMANIA_SUFFIX)].strip()
    return first or None


def normalize_remote(value: str | None) -> str | None:
    """Normalizeaza la exact on-site / hybrid / remote; orice altceva -> None."""
    if not value or not isinstance(value, str):
        return None
    return _REMOTE_MAP.get(value.strip().lower())


def raw_job_from_peviitor_doc(doc: dict) -> RawJob | None:
    """Construieste un RawJob dintr-un doc peViitor. Fara url, se arunca."""
    url = doc.get("url")
    if not isinstance(url, str) or not url.strip():
        return None

    # doc-urile au si "workmode" si "remote"; workmode e formatul asteptat
    # (on-site/hybrid/remote), "remote" e cazut ca rezerva daca workmode lipseste.
    remote = normalize_remote(doc.get("workmode")) or normalize_remote(doc.get("remote"))

    return RawJob(
        url=url.strip(),
        title=normalize_text(doc.get("title")),
        company=normalize_text(doc.get("company")),
        city=normalize_city(doc.get("city")),
        remote=remote,
        source="peviitor",
    )
