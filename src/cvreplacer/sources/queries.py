"""Genereaza interogarile de recoltare din profile.json.

Ordinea de prioritate (spec R3): competente cautabile, titluri de rol RO/EN,
termeni de domeniu. Niciun termen concret nu e scris literal in cod - totul
vine din profil, titlurile fiind extinse printr-o lista mica de traduceri
dintr-un fisier separat de date (role_translations.py). Un profil diferit
produce alte interogari fara nicio modificare de cod.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cvreplacer.sources.role_translations import ROLE_TYPE_TRANSLATIONS

MAX_QUERIES = 30

# Competentele cu peste atatea cuvinte sunt de regula descrieri, nu termeni
# de cautare plauzibili (ex. "cost and token budgeting" vs. "FastAPI").
_MAX_SKILL_WORDS = 2


def load_profile(path: str | Path) -> dict[str, Any]:
    """Citeste profile.json. Nu face nicio validare de continut aici."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_queries(profile: dict[str, Any]) -> list[str]:
    """Produce cel mult MAX_QUERIES interogari, deduplicate, in ordinea de prioritate."""
    cv = profile.get("cv", {})

    terms: list[str] = []
    terms.extend(_searchable_skills(cv.get("skills", [])))
    terms.extend(_role_titles(profile, cv))
    terms.extend(_domain_terms(cv.get("domain_knowledge", [])))

    return _dedupe(terms)[:MAX_QUERIES]


def _searchable_skills(skills: list[dict[str, Any]]) -> list[str]:
    terms = []
    for skill in skills:
        name = skill.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if len(name.split()) <= _MAX_SKILL_WORDS:
            terms.append(name.strip())
    return terms


def _role_titles(profile: dict[str, Any], cv: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    headline = profile.get("identity", {}).get("headline")
    if isinstance(headline, str) and headline.strip():
        roles.append(headline.strip())
    for exp in cv.get("experience", []):
        role = exp.get("role")
        if isinstance(role, str) and role.strip():
            roles.append(role.strip())
    roles = _dedupe(roles)

    titles: list[str] = []
    for role in roles:
        titles.append(role)
        translated = _translate_role(role)
        if translated:
            titles.append(translated)
    return titles


def _translate_role(role: str) -> str | None:
    """Traduce doar tipul rolului (ultimul cuvant), pastrand restul neschimbat.

    'AI Engineer' -> 'inginer AI'. Daca ultimul cuvant nu e cunoscut, nu se
    produce nicio traducere - mai bine lipseste o interogare decat sa iasa
    un termen stricat.
    """
    words = role.split()
    if len(words) < 2:
        return None
    last = words[-1].lower().strip(",.")
    translation = ROLE_TYPE_TRANSLATIONS.get(last)
    if translation is None:
        return None
    prefix = " ".join(words[:-1])
    return f"{translation} {prefix}".strip()


def _domain_terms(domain_knowledge: list[dict[str, Any]]) -> list[str]:
    terms = []
    for entry in domain_knowledge:
        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            terms.append(name.strip())
    return terms


def _dedupe(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        key = term.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(term.strip())
    return result
