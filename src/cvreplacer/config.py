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


@dataclass(frozen=True)
class FreehireConfig:
    base: str
    country: str
    posted_within_days: int
    max_pages: int


def load_freehire_config() -> FreehireConfig:
    """Citeste variabilele sursei freehire. Eroare clara daca lipseste baza."""
    return FreehireConfig(
        base=_require("CVR_FREEHIRE_BASE"),
        country=os.environ.get("CVR_FREEHIRE_COUNTRY", "ro"),
        posted_within_days=int(os.environ.get("CVR_FREEHIRE_POSTED_WITHIN_DAYS", "30")),
        max_pages=int(os.environ.get("CVR_FREEHIRE_MAX_PAGES", "3")),
    )


@dataclass(frozen=True)
class LocationConfig:
    home_city: str
    accept_remote: bool
    accept_hybrid_home_only: bool
    extra_cities: list[str]


def load_location_config() -> LocationConfig:
    """Citeste variabilele necesare filtrului de locatie (filters/location.py)."""
    return LocationConfig(
        home_city=_require("CVR_HOME_CITY"),
        accept_remote=_bool_env("CVR_ACCEPT_REMOTE", default=True),
        accept_hybrid_home_only=_bool_env("CVR_ACCEPT_HYBRID_HOME_ONLY", default=True),
        extra_cities=_csv_env("CVR_EXTRA_CITIES"),
    )


@dataclass(frozen=True)
class CompanyCapConfig:
    max_per_company: int


def load_company_cap_config() -> CompanyCapConfig:
    """Citeste plafonul per companie folosit de filters/company_cap.py."""
    return CompanyCapConfig(max_per_company=int(os.environ.get("CVR_MAX_PER_COMPANY", "3")))


@dataclass(frozen=True)
class FetchConfig:
    user_agent: str
    timeout_s: float
    rate_limit_s: float
    concurrency: int
    cache_dir: str
    cache_ttl_days: int
    max_description_chars: int


def load_fetch_config() -> FetchConfig:
    """Citeste variabilele necesare comenzii fetch (descarcarea descrierilor, E5)."""
    return FetchConfig(
        user_agent=_require("CVR_USER_AGENT"),
        timeout_s=float(os.environ.get("CVR_FETCH_TIMEOUT_S", "20")),
        rate_limit_s=float(os.environ.get("CVR_RATE_LIMIT_SECONDS", "1.0")),
        concurrency=int(os.environ.get("CVR_FETCH_CONCURRENCY", "4")),
        cache_dir=os.environ.get("CVR_CACHE_DIR", "data/cache"),
        cache_ttl_days=int(os.environ.get("CVR_CACHE_TTL_DAYS", "14")),
        max_description_chars=int(os.environ.get("CVR_MAX_DESCRIPTION_CHARS", "20000")),
    )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"lipseste variabila de mediu {name} (vezi .env.example)")
    return value


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip() not in ("0", "false", "False")


def _csv_env(name: str) -> list[str]:
    value = os.environ.get(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]
