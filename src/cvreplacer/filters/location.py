"""Filtrul 'location': oras de domiciliu si mod de lucru.

Reguli (docs/handoff/E4-coder.md):
- remote trece intotdeauna daca CVR_ACCEPT_REMOTE e activ;
- mod de lucru necunoscut (None) trece - nu taiem pe lipsa de date;
- hybrid si on-site trec doar pentru orasul de domiciliu sau CVR_EXTRA_CITIES;
- daca CVR_ACCEPT_HYBRID_HOME_ONLY e dezactivat, hybrid e tratat ca remote
  (acceptat oriunde) - doar on-site mai cere potrivire de oras.

Orasele din jobs.city pot fi o lista separata prin virgula (ex. sursa pune
mai multe orase intr-un singur camp). Daca oricare se potriveste, trece.
Compararea ignora diacriticele, prin filters.fold.
"""

from __future__ import annotations

from collections.abc import Sequence

from cvreplacer.config import LocationConfig
from cvreplacer.filters import FilterStep, fold
from cvreplacer.storage.models import JobRow

# Valori care apar in campul city al sursei si care nu numesc un oras anume.
_WILDCARD_CITIES = {"all", "remote", "romania"}


def make_location_filter(config: LocationConfig) -> FilterStep:
    allowed_cities = {fold(config.home_city)} | {fold(c) for c in config.extra_cities}

    def _city_matches(city: str | None) -> bool:
        # Nu taiem pe lipsa de date: un anunt fara oras completat nu e un anunt
        # din alt oras, e un anunt despre care nu stim. Verificat in datele
        # reale - 11 anunturi Python aveau city=None si 13 aveau "all".
        if not city:
            return True
        parts = [fold(part) for part in city.split(",") if part.strip()]
        if not parts:
            return True
        # Valori speciale din sursa: "all" inseamna toate orasele, "remote" si
        # "romania" nu numesc un oras anume.
        if any(part in _WILDCARD_CITIES for part in parts):
            return True
        return any(part in allowed_cities for part in parts)

    def _apply(jobs: Sequence[JobRow]) -> list[JobRow]:
        kept: list[JobRow] = []
        for job in jobs:
            remote = job.remote

            if remote is None:
                # Mod de lucru necunoscut: aceeasi regula, nu taiem pe lipsa.
                kept.append(job)
                continue

            if remote == "remote":
                if config.accept_remote:
                    kept.append(job)
                continue

            if remote == "hybrid" and not config.accept_hybrid_home_only:
                # Hibridul acceptat oriunde se comporta ca remote.
                kept.append(job)
                continue

            # Ramane on-site, si hibridul legat de orasul de domiciliu.
            if _city_matches(job.city):
                kept.append(job)
        return kept

    return FilterStep(name="location", fn=_apply)
