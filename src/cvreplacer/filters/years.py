"""Filtrul 'years': cerinta de ani din text, comparata PE DOMENIU (spec.md R9b).

Ruleaza pe raw_text, deci dupa descarcarea descrierii (E5) - nu in lantul de
metadate de dinaintea fetch-ului. Se aplica separat, cu apply_chain (acelasi
mecanism, un singur filtru).

Pragurile vin din data/cv/profile.json (experience_years), la rulare - nu
sunt codificate aici si nu vin din .env, ca sa nu existe doua surse de
adevar pentru un numar care descrie o persoana anume.

Regula de prudenta, obligatorie: se taie DOAR cazurile clare - o cerinta
explicit software/AI peste pragul ai_software. Orice e ambiguu (domeniu
neclar, generic, sau clar inginerie) TRECE si se decide la scoring. Un
anunt bun ratat de o expresie regulata prea agresiva costa mai mult decat
cativa centi in plus la model.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from cvreplacer.filters import FilterStep, fold
from cvreplacer.storage.models import JobRow

# Fereastra de text din jurul cerintei de ani, in care cautam cuvinte de
# domeniu. Suficient de mica cat sa nu prinda alta propozitie din anunt.
_CONTEXT_WINDOW = 60

# Cuvinte care marcheaza clar domeniul software/AI. Lista deliberat scurta:
# vrem doar cazurile clare, nu orice mentiune indirecta.
_AI_SOFTWARE_KEYWORDS = [
    "python", "java", "javascript", "typescript", "software", "programare",
    "developer", "dezvoltator", "backend", "frontend", "full stack",
    "fullstack", "devops", "machine learning", "inteligenta artificiala",
    " ai ", "data science", "sql", ".net", "c++", "c#", "php", "react",
    "angular", "node.js", "nodejs", "cod", "coding", "dezvoltare software",
    "software development", "web development", "dezvoltare web",
]

# Cerintele de ani, in formele intalnite real (RO + EN). Lucreaza pe text
# deja "fold"-uit (litere mici, fara diacritice).
_YEARS_PATTERNS = [
    # "minim 3 ani", "minimum 3 ani", "cel putin 3 ani", "peste 3 ani",
    # opt. interval: "minim 3-5 ani". Acopera si "experienta de minim 2 ani"
    # (prefixul "experienta de" nu conteaza, regexul cauta doar "minim 2 ani").
    re.compile(
        r"(?:minim(?:um)?|cel putin|peste)\s+(\d{1,2})"
        r"(?:\s*[-–]\s*(\d{1,2}))?\s*(?:ani|an|years?|yrs?)\b"
    ),
    # "3+ ani", "3+ years"
    re.compile(r"\b(\d{1,2})\s*\+\s*(?:ani|an|years?|yrs?)\b"),
    # "3-5 ani", "3-5 years", fara alt prefix
    re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:ani|an|years?|yrs?)\b"),
    # "3 ani experienta", "3 ani de experienta"
    re.compile(r"\b(\d{1,2})\s*(?:ani|an)\s+(?:de\s+)?experient\w*\b"),
    # "3 years experience", "3 years of experience"
    re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b"),
]


@dataclass(frozen=True)
class YearsThresholds:
    """Pragurile de ani, pe domeniu - extrase din profile.json la rulare."""

    total_professional: float
    ai_software: float
    engineering_design: float


def thresholds_from_profile(profile: dict) -> YearsThresholds:
    """Construieste pragurile din profile.json (experience_years)."""
    experience_years = profile["experience_years"]
    by_domain = experience_years["by_domain"]
    return YearsThresholds(
        total_professional=experience_years["total_professional"],
        ai_software=by_domain["ai_software"],
        engineering_design=by_domain["engineering_design"],
    )


def _lower_bound(match: re.Match[str]) -> int:
    groups = [g for g in match.groups() if g is not None]
    return min(int(g) for g in groups)


def _is_ai_software_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - _CONTEXT_WINDOW) : end + _CONTEXT_WINDOW]
    return any(keyword in window for keyword in _AI_SOFTWARE_KEYWORDS)


def has_clear_ai_software_overage(text: str, threshold: float) -> bool:
    """True doar daca textul cere explicit ani de software/AI peste prag.

    Orice alt caz (fara mentiune de ani, domeniu generic sau de inginerie,
    ori sub prag) intoarce False - filtrul nu taie decat ce e clar.
    """
    folded = fold(text)
    for pattern in _YEARS_PATTERNS:
        for match in pattern.finditer(folded):
            years = _lower_bound(match)
            if years > threshold and _is_ai_software_context(folded, match.start(), match.end()):
                return True
    return False


def make_years_filter(thresholds: YearsThresholds) -> FilterStep:
    def _apply(jobs: Sequence[JobRow]) -> list[JobRow]:
        kept = []
        for job in jobs:
            if job.raw_text and has_clear_ai_software_overage(job.raw_text, thresholds.ai_software):
                continue
            kept.append(job)
        return kept

    return FilterStep(name="years", fn=_apply)
