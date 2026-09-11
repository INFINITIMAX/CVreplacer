"""Extragerea textului principal dintr-o pagina HTML de anunt (brief E5).

Elimina zgomotul (scripturi, navigatie, subsol), pastreaza paragrafele,
limiteaza lungimea - anunturile lungi cu subsol juridic nu au ce cauta
la scoring, iar tokenii costa.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Sub atatea caractere, textul extras e tratat ca esec de extragere -
# probabil pagina e randata din JavaScript (brief E5).
_MIN_CHARS = 200

_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "form", "noscript")

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

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


def extract_text(html: str, max_chars: int) -> str:
    """Textul principal din html, curatat si limitat la max_chars caractere."""
    tree = HTMLParser(html)
    for tag in _STRIP_TAGS:
        for node in tree.css(tag):
            node.decompose()

    container = _pick_main_container(tree)
    raw_text = container.text(separator="\n") if container is not None else ""
    text = _collapse_whitespace(raw_text)
    return text[:max_chars]


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
