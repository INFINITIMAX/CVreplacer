"""Normalizarea campurilor brute de la surse, comuna tuturor surselor.

Fiecare sursa produce RawJob (definit in storage.models) prin functiile
de aici, ca formatul sa fie identic indiferent de unde vine anuntul.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from cvreplacer.storage.models import RawJob

_ROMANIA_SUFFIX = ", Romania"

# Taguri dupa care se pune linie noua, ca blocurile sa nu se lipeasca intre ele.
_BLOCK_BREAK_RE = re.compile(
    r"<br\s*/?>|</?(?:p|div|li|ul|ol|h[1-6]|tr|table|section|article)\b[^>]*>",
    re.IGNORECASE,
)

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


def html_to_text(fragment: str, max_chars: int) -> str:
    """Text simplu dintr-un fragment HTML, cu linii noi intre blocuri, taiat la max_chars."""
    if not fragment or not fragment.strip():
        return ""

    marked = _BLOCK_BREAK_RE.sub("\n", fragment)
    tree = HTMLParser(marked)
    for tag in ("script", "style"):
        for node in tree.css(tag):
            node.decompose()
    body = tree.body
    raw = body.text(separator="") if body is not None else ""

    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in raw.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:max_chars]


def _strip_utm(url: str) -> str:
    """Scoate parametrii utm_* din query; restul ramane neschimbat."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [p for p in parts.query.split("&") if p and not p.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query="&".join(kept)))


def raw_job_from_freehire_doc(doc: dict, max_chars: int) -> RawJob | None:
    """Construieste un RawJob dintr-un element freehire. Fara url sau inchis, se arunca."""
    url = doc.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    if doc.get("closed_at"):
        return None

    description = doc.get("description")
    raw_text = html_to_text(description, max_chars) if isinstance(description, str) else ""

    return RawJob(
        url=_strip_utm(url.strip()),
        title=normalize_text(doc.get("title")),
        company=normalize_text(doc.get("company")),
        city=normalize_city(doc.get("cities")),
        remote=None,
        source="freehire",
        raw_text=raw_text or None,
    )


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
