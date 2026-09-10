"""Lipirea manuala a unui anunt: acelasi contract RawJob ca peViitor."""

from __future__ import annotations

from cvreplacer.sources.base import normalize_text
from cvreplacer.storage.models import RawJob


def from_pasted_text(url: str, text: str) -> RawJob:
    """Construieste un RawJob din url + text lipit de utilizator.

    Titlul si compania se incearca din primele doua linii nevide; daca
    textul nu are destule linii, raman goale si se completeaza in interfata.
    """
    if not url or not url.strip():
        raise ValueError("url e obligatoriu pentru un anunt lipit manual")

    lines = [normalize_text(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]

    title = lines[0] if len(lines) >= 1 else ""
    company = lines[1] if len(lines) >= 2 else ""

    return RawJob(
        url=url.strip(),
        title=title,
        company=company,
        city=None,
        remote=None,
        source="manual",
        raw_text=text,
    )
