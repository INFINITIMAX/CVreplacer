"""Filtrul 'dedup': acelasi job, anunturi diferite (republicari).

Cheia: (titlu normalizat, companie normalizata). Normalizare: litere mici,
fara diacritice, fara punctuatie, spatii colapsate, si eliminarea codurilor
de referinta din titlu (ex. IRC300958, ID208262 - apar frecvent in date si
ar transforma acelasi anunt republicat in chei diferite).

Cand exista duplicate, se pastreaza cel cu first_seen cel mai vechi - e
anuntul original, celelalte sunt republicari.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from cvreplacer.filters import FilterStep, fold
from cvreplacer.storage.models import JobRow

# Coduri de referinta tip IRC300958, ID208262: litere urmate de cifre lungi.
_REFERENCE_CODE = re.compile(r"\b[a-z]{1,6}\d{3,}\b")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    text = fold(title)
    text = _REFERENCE_CODE.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def normalize_company(company: str) -> str:
    text = fold(company)
    text = _NON_ALNUM.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def make_dedup_filter() -> FilterStep:
    def _apply(jobs: Sequence[JobRow]) -> list[JobRow]:
        best_by_key: dict[tuple[str, str], JobRow] = {}
        for job in jobs:
            key = (normalize_title(job.title), normalize_company(job.company))
            current_best = best_by_key.get(key)
            if current_best is None or job.first_seen < current_best.first_seen:
                best_by_key[key] = job
        kept_urls = {job.url for job in best_by_key.values()}
        return [job for job in jobs if job.url in kept_urls]

    return FilterStep(name="dedup", fn=_apply)
