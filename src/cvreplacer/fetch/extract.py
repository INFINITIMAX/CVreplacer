"""Extragerea textului principal dintr-o pagina HTML de anunt (brief E5).

Elimina zgomotul (scripturi, navigatie, subsol), pastreaza paragrafele,
limiteaza lungimea - anunturile lungi cu subsol juridic nu au ce cauta
la scoring, iar tokenii costa.
"""

from __future__ import annotations

import re

import trafilatura
from selectolax.parser import HTMLParser

# Sub atatea caractere, textul extras e tratat ca esec de extragere -
# probabil pagina e randata din JavaScript (brief E5).
_MIN_CHARS = 200

# "aside" lipsea: reviewer-ul a aratat ca meniul lateral ajungea in text.
_STRIP_TAGS = (
    "script", "style", "nav", "header", "footer", "form", "noscript", "aside",
)

# Selectoare candidate pentru containerul principal, in ordinea in care le
# incercam. Lista deliberat scurta - eticheta si atribute uzuale pentru
# descrieri de anunt, nu o euristica generica de "reader mode".
_CANDIDATE_SELECTORS = (
    "main",
    "article",
    "[role=main]",
    "[id*=content]",
    "[class*=content]",
    "[id*=description]",
    "[class*=description]",
)

# Un candidat e preferat body-ului doar daca acopera macar atata din textul
# total - altfel un container gasit gresit (ex. un mic bloc "content" din
# antet) ar taia restul descrierii.
_MIN_DENSITY_RATIO = 0.3

# Sub atata din lungimea variantei de rezerva, consideram ca trafilatura a
# taiat continut real, nu crom. Masurat: 2 pagini din 54.
_FALLBACK_RATIO = 0.35

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


def extract_text(html: str, max_chars: int) -> str:
    """Textul principal din html, curatat si limitat la max_chars caractere.

    Doua straturi, in ordinea asta:

    1. trafilatura cu favor_precision - algoritm de extragere a continutului
       principal, intretinut, care nu depinde de selectoare scrise de noi.
       Masurat pe 54 de pagini reale din cache: fragmentele de crom scad de la
       21 la 6 (-71%) la acelasi cost in caractere. Fara el, meniul lateral
       ("Entry level (< 2 Ani) Medium level (2-5 Ani)") ajunge in text, unde
       polueaza filtrul de ani si se plateste ca tokeni la scoring.
    2. euristica proprie pe selectolax, ca rezerva. Pe 2 din 54 de pagini
       trafilatura pastra sub 35% din text; acolo varianta locala e mai buna.

    Nu alegem "biblioteca peste euristica" din principiu, ci pentru ca avem
    ~200 de domenii distincte si nu putem scrie selectoare pentru fiecare.
    """
    precise = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    fallback = _extract_with_selectolax(html)

    # Rezerva intra doar cand trafilatura pierde evident continut, nu cand e
    # doar mai concisa - altfel am anula exact castigul de precizie.
    text = precise or ""
    if not text or (fallback and len(text) < _FALLBACK_RATIO * len(fallback)):
        text = fallback

    return _collapse_whitespace(text)[:max_chars]


def _extract_with_selectolax(html: str) -> str:
    tree = HTMLParser(html)
    for tag in _STRIP_TAGS:
        for node in tree.css(tag):
            node.decompose()

    container = _pick_main_container(tree)
    raw_text = container.text(separator="\n") if container is not None else ""
    return _collapse_whitespace(raw_text)


def is_too_short(text: str) -> bool:
    """True daca textul extras e sub pragul minim - tratat ca esec de extragere."""
    return len(text) < _MIN_CHARS


def _pick_main_container(tree: HTMLParser):
    body = tree.body
    if body is None:
        return None

    best = None
    best_len = 0
    for selector in _CANDIDATE_SELECTORS:
        for node in tree.css(selector):
            length = len(node.text(separator=" ", strip=True))
            if length > best_len:
                best = node
                best_len = length

    body_len = len(body.text(separator=" ", strip=True))
    if best is not None and body_len > 0 and best_len / body_len >= _MIN_DENSITY_RATIO:
        return best
    return body


def _collapse_whitespace(text: str) -> str:
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in text.splitlines()]
    collapsed = "\n".join(lines)
    collapsed = _MULTI_BLANK_LINES.sub("\n\n", collapsed)
    return collapsed.strip()
