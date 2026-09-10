"""Configurare citita din mediu, prin .env. Fara valori codificate in sursa."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class HarvestConfig:
    peviitor_base: str
    user_agent: str
    rate_limit_s: float
    db_path: str


def load_harvest_config() -> HarvestConfig:
    """Citeste variabilele necesare comenzii harvest. Eroare clara daca lipsesc."""
    return HarvestConfig(
        peviitor_base=_require("CVR_PEVIITOR_BASE"),
        user_agent=_require("CVR_USER_AGENT"),
        rate_limit_s=float(os.environ.get("CVR_RATE_LIMIT_SECONDS", "1.0")),
        db_path=os.environ.get("CVR_DB_PATH", "data/cvreplacer.db"),
    )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"lipseste variabila de mediu {name} (vezi .env.example)")
    return value
