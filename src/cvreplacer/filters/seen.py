"""Filtrul 'seen': taie anunturile deja scorate cu aceeasi versiune de prompt.

Cheia e compusa (url, prompt_version) - vezi storage/schema.py, tabela scores.
Un anunt scorat cu o rubrica veche (prompt_version diferit) trebuie re-scorat,
de asta comparatia nu se face doar pe url.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from cvreplacer.filters import FilterStep
from cvreplacer.storage.models import JobRow


def make_seen_filter(conn: sqlite3.Connection, prompt_version: str) -> FilterStep:
    """Citeste o singura data urlurile deja scorate cu prompt_version si construieste filtrul."""
    rows = conn.execute(
        "SELECT url FROM scores WHERE prompt_version = ?", (prompt_version,)
    ).fetchall()
    scored_urls = {row["url"] for row in rows}

    def _apply(jobs: Sequence[JobRow]) -> list[JobRow]:
        return [job for job in jobs if job.url not in scored_urls]

    return FilterStep(name="seen", fn=_apply)
