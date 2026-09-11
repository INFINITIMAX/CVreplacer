"""Teste pentru cvreplacer.sources.base — normalizarea comuna tuturor surselor.

Cazurile vin din date reale (docs/handoff/E3-E4-tester.md), nu inventate.
"""

from __future__ import annotations

from cvreplacer.sources.base import (
    normalize_city,
    normalize_remote,
    normalize_text,
    raw_job_from_peviitor_doc,
)

# --------------------------------------------------------------------------
# normalize_city
# --------------------------------------------------------------------------


def test_city_list_with_romania_suffix_strips_it():
    assert normalize_city(["Bucuresti, Romania"]) == "Bucuresti"


def test_city_list_with_only_romania_is_none():
    assert normalize_city(["Romania"]) is None


def test_city_multi_town_string_kept_whole():
    assert normalize_city(["Iasi,Targu-Mures,Bucuresti"]) == "Iasi,Targu-Mures,Bucuresti"


def test_city_none_input_is_none():
    assert normalize_city(None) is None


def test_city_empty_list_is_none():
    assert normalize_city([]) is None


def test_city_blank_string_is_none():
    assert normalize_city(["   "]) is None


def test_city_non_string_first_element_is_none():
    # datele brute pot avea un element neasteptat (ex. un numar); nu trebuie sa crape.
    assert normalize_city([123]) is None  # type: ignore[list-item]


# --------------------------------------------------------------------------
# normalize_remote
# --------------------------------------------------------------------------


def test_remote_on_site_variants_normalize_to_on_site():
    assert normalize_remote("on-site") == "on-site"
    assert normalize_remote("onsite") == "on-site"
    assert normalize_remote("on site") == "on-site"


def test_remote_hybrid_variants_normalize_to_hybrid():
    assert normalize_remote("hybrid") == "hybrid"
    assert normalize_remote("hibrid") == "hybrid"


def test_remote_value_normalizes_to_remote():
    assert normalize_remote("remote") == "remote"


def test_remote_is_case_and_space_insensitive():
    assert normalize_remote("  REMOTE  ") == "remote"


def test_remote_unknown_value_is_none():
    assert normalize_remote("banana") is None


def test_remote_none_is_none():
    assert normalize_remote(None) is None


def test_remote_non_string_is_none():
    assert normalize_remote(123) is None  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# normalize_text
# --------------------------------------------------------------------------


def test_text_html_entity_decoded():
    assert normalize_text("Dezvoltator &amp; Administrator") == "Dezvoltator & Administrator"


def test_text_multiple_spaces_collapsed_and_stripped():
    assert normalize_text("  Python   Developer  ") == "Python Developer"


def test_text_none_is_empty_string():
    assert normalize_text(None) == ""


def test_text_blank_string_is_empty_string():
    assert normalize_text("   ") == ""


# --------------------------------------------------------------------------
# raw_job_from_peviitor_doc
# --------------------------------------------------------------------------


def test_doc_without_url_is_discarded():
    doc = {"title": "Python Developer", "company": "Exemplu SRL"}
    assert raw_job_from_peviitor_doc(doc) is None


def test_doc_with_blank_url_is_discarded():
    doc = {"url": "   ", "title": "Python Developer"}
    assert raw_job_from_peviitor_doc(doc) is None


def test_doc_with_non_string_url_is_discarded():
    doc = {"url": 12345}
    assert raw_job_from_peviitor_doc(doc) is None


def test_doc_workmode_used_when_present():
    doc = {"url": "https://exemplu.test/1", "workmode": "remote", "remote": "hybrid"}
    job = raw_job_from_peviitor_doc(doc)
    assert job is not None
    assert job.remote == "remote"  # workmode are prioritate fata de remote


def test_doc_falls_back_to_remote_field_when_workmode_missing():
    doc = {"url": "https://exemplu.test/1", "remote": "hibrid"}
    job = raw_job_from_peviitor_doc(doc)
    assert job is not None
    assert job.remote == "hybrid"


def test_doc_produces_normalized_fields_and_source_peviitor():
    doc = {
        "url": "https://exemplu.test/1",
        "title": "Python &amp;  Django  Developer",
        "company": "  Exemplu  SRL  ",
        "city": ["Cluj-Napoca, Romania"],
        "workmode": "on-site",
    }
    job = raw_job_from_peviitor_doc(doc)
    assert job is not None
    assert job.url == "https://exemplu.test/1"
    assert job.title == "Python & Django Developer"
    assert job.company == "Exemplu SRL"
    assert job.city == "Cluj-Napoca"
    assert job.remote == "on-site"
    assert job.source == "peviitor"
