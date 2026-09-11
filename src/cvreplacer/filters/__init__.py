"""Lantul de filtre ieftine, care ruleaza inaintea oricarui apel platit.

Ordinea (spec.md R6, sectiunea 2.1) e arhitectura, nu o optimizare:
deja vazute -> locatie -> deduplicare -> plafon per companie -> ani ceruti.
Fiecare filtru e o functie simpla (JobRow-uri intra, JobRow-uri ies) si
apply_chain aduna raportul din diferenta intre ce a intrat si ce a iesit.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cvreplacer.storage.models import JobRow

# Cate titluri de exemplu pastram per filtru, pentru depanare. Nu tot ce s-a
# taiat - doar cateva, cat sa se vada tiparul fara sa umfle raportul.
_MAX_EXAMPLES = 5

FilterFn = Callable[[Sequence[JobRow]], list[JobRow]]


@dataclass(frozen=True)
class FilterStep:
    """Un filtru numit, gata de pus in lant."""

    name: str
    fn: FilterFn


@dataclass(frozen=True)
class FilterReport:
    """Cate a lasat sa treaca fiecare filtru, pentru --dry-run din E6."""

    name: str
    n_in: int
    n_out: int
    n_cut: int
    examples_cut: list[str]


def apply_chain(
    jobs: Sequence[JobRow], filters: Sequence[FilterStep]
) -> tuple[list[JobRow], list[FilterReport]]:
    """Aplica filtrele in ordine; fiecare vede doar ce a lasat cel dinaintea lui.

    Daca un filtru tace si lasa sa treaca tot, raportul lui arata n_cut = 0
    si asta e semnalul ca ceva nu functioneaza cum trebuie (spec.md conflict #3).
    """
    current = list(jobs)
    reports: list[FilterReport] = []
    for step in filters:
        kept = step.fn(current)
        kept_urls = {job.url for job in kept}
        cut = [job for job in current if job.url not in kept_urls]
        reports.append(
            FilterReport(
                name=step.name,
                n_in=len(current),
                n_out=len(kept),
                n_cut=len(cut),
                examples_cut=[job.title for job in cut[:_MAX_EXAMPLES]],
            )
        )
        current = kept
    return current, reports


def fold(text: str) -> str:
    """Litere mici, fara diacritice. Folosit de location, dedup si years:
    aceleasi date apar uneori cu diacritice, uneori fara, in functie de sursa.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()
