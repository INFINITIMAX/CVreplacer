"""Sinonime si traduceri folosite la generarea interogarilor din profil.

Generic, nu specific unui profil: mapeaza ultimul cuvant al unui titlu de
rol (engleza) la echivalentul romanesc al tipului de rol. Restul titlului
(ex. "AI", "Python", "Backend") ramane neschimbat, pentru ca sunt deja
termeni cautabili in ambele limbi.
"""

from __future__ import annotations

ROLE_TYPE_TRANSLATIONS: dict[str, str] = {
    "engineer": "inginer",
    "developer": "programator",
    "manager": "manager",
    "architect": "arhitect",
    "analyst": "analist",
    "scientist": "cercetator",
    "designer": "proiectant",
}
