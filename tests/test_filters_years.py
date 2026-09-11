"""Teste pentru filters.years — filtrul cel mai periculos, taie doar cazuri clare.

Textele sunt fabricate (nu exista inca descrieri reale, vin la E5), dar folosesc
exact formularile din docs/handoff/E3-E4-tester.md. Praguri: total=6.2,
ai_software=0.6, engineering_design=5.4 (din brief).
"""

from __future__ import annotations

from conftest import make_job_row

from cvreplacer.filters.years import (
    YearsThresholds,
    has_clear_ai_software_overage,
    make_years_filter,
    thresholds_from_profile,
)

_THRESHOLDS = YearsThresholds(total_professional=6.2, ai_software=0.6, engineering_design=5.4)


def _overage(text: str, threshold: float = _THRESHOLDS.ai_software) -> bool:
    return has_clear_ai_software_overage(text, threshold)


# --------------------------------------------------------------------------
# tabelul din brief
# --------------------------------------------------------------------------


def test_generic_minim_3_ani_passes_total_covers_it():
    assert _overage("minim 3 ani experienta") is False


def test_generic_3_plus_years_of_experience_passes():
    assert _overage("3+ years of experience") is False


def test_software_3_ani_python_is_cut():
    assert _overage("3 ani experienta in Python") is True


def test_software_5_plus_years_development_is_cut():
    assert _overage("5+ years software development") is True


def test_engineering_5_years_design_passes_engineering_covers_it():
    assert _overage("experienta in proiectare de minim 5 ani") is False


def test_no_years_mention_passes():
    assert _overage("cautam un coleg pasionat si dedicat") is False


def test_ambiguous_wording_passes_precaution_rule():
    # nicio expresie numerica de ani, doar text vag - regula de prudenta: trece.
    assert _overage("experienta relevanta in domeniu, fara cerinte stricte") is False


def test_ambiguous_generic_years_without_domain_keyword_passes():
    # mentioneaza ani, dar contextul nu e nici software/AI, nici inginerie -
    # regula de prudenta: nu taiem cand domeniul e neclar.
    assert _overage("minim 3 ani experienta in domeniul administrativ") is False


def test_range_uses_lower_bound_not_upper_bound():
    # "3-5 ani" trebuie evaluat pe limita inferioara (3), nu pe cea superioara (5).
    # cu un prag de 4.0: 3 nu depaseste -> nu se taie. Daca implementarea ar folosi
    # limita superioara (5 > 4.0), testul ar cadea aici.
    text = "3-5 ani experienta in Python"
    assert has_clear_ai_software_overage(text, threshold=4.0) is False
    # cu un prag de 2.0, limita inferioara (3) chiar depaseste -> se taie.
    assert has_clear_ai_software_overage(text, threshold=2.0) is True


# --------------------------------------------------------------------------
# thresholds_from_profile
# --------------------------------------------------------------------------


def test_thresholds_from_profile_reads_by_domain_values():
    profile = {
        "experience_years": {
            "total_professional": 6.2,
            "by_domain": {"ai_software": 0.6, "engineering_design": 5.4},
        }
    }
    thresholds = thresholds_from_profile(profile)
    assert thresholds.total_professional == 6.2
    assert thresholds.ai_software == 0.6
    assert thresholds.engineering_design == 5.4


# --------------------------------------------------------------------------
# integrare: make_years_filter
# --------------------------------------------------------------------------


def test_filter_cuts_job_with_clear_software_overage():
    job = make_job_row(
        url="https://exemplu.test/1", raw_text="Cerinte: 5+ years software development"
    )
    step = make_years_filter(_THRESHOLDS)
    kept = step.fn([job])
    assert kept == []


def test_filter_keeps_job_with_ambiguous_or_generic_text():
    job = make_job_row(url="https://exemplu.test/1", raw_text="minim 3 ani experienta")
    step = make_years_filter(_THRESHOLDS)
    kept = step.fn([job])
    assert len(kept) == 1


def test_filter_keeps_job_without_raw_text():
    # nicio descriere descarcata inca (dinainte de E5) - nu putem evalua, deci trece.
    job = make_job_row(url="https://exemplu.test/1", raw_text=None)
    step = make_years_filter(_THRESHOLDS)
    kept = step.fn([job])
    assert len(kept) == 1
