"""Teste E3F pentru sources/base.py: html_to_text, _strip_utm, raw_job_from_freehire_doc."""

from __future__ import annotations

import pytest

from cvreplacer.sources.base import _strip_utm, html_to_text, raw_job_from_freehire_doc

# --------------------------------------------------------------------------
# html_to_text
# --------------------------------------------------------------------------


def test_paragraphs_end_up_on_separate_lines():
    lines = html_to_text("<p>a</p><p>b</p>", 1000).splitlines()
    assert "a" in lines
    assert "b" in lines


def test_list_items_on_separate_lines():
    lines = html_to_text("<ul><li>unu</li><li>doi</li><li>trei</li></ul>", 1000).splitlines()
    assert "unu" in lines
    assert "doi" in lines
    assert "trei" in lines


@pytest.mark.parametrize("br", ["<br>", "<br/>", "<br />", "<BR>"])
def test_br_becomes_newline(br):
    assert html_to_text(f"prima{br}a doua", 1000).splitlines() == ["prima", "a doua"]


def test_entities_are_decoded():
    assert html_to_text("<p>Tom &amp; Jerry</p>", 1000) == "Tom & Jerry"


def test_nbsp_becomes_plain_space():
    text = html_to_text("<p>a&nbsp;b</p>", 1000)
    assert "\xa0" not in text
    assert text == "a b"


def test_script_and_style_content_removed():
    text = html_to_text(
        "<p>vizibil</p><script>alert('secret')</script><style>.x{color:red}</style>", 1000
    )
    assert "vizibil" in text
    assert "alert" not in text
    assert "color" not in text


def test_plain_text_without_tags_is_returned():
    assert html_to_text("doar text simplu", 1000) == "doar text simplu"


@pytest.mark.parametrize("empty", ["", "   ", "\n\t"])
def test_empty_or_blank_input_gives_empty_string(empty):
    assert html_to_text(empty, 1000) == ""


def test_output_truncated_to_max_chars():
    text = html_to_text("<p>" + "x" * 500 + "</p>", 40)
    assert len(text) == 40


def test_short_text_not_padded_or_cut_by_large_max_chars():
    assert html_to_text("<p>scurt</p>", 10000) == "scurt"


def test_many_consecutive_blocks_do_not_produce_more_than_one_blank_line():
    text = html_to_text("<p>a</p><div></div><div></div><p></p><p>b</p>", 1000)
    assert "\n\n\n" not in text


# --------------------------------------------------------------------------
# _strip_utm
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://exemplu.test/j?utm_source=freehire.me", "https://exemplu.test/j"),
        ("https://exemplu.test/j?gh_jid=123&utm_source=x", "https://exemplu.test/j?gh_jid=123"),
        ("https://exemplu.test/j?utm_source=x&gh_jid=123", "https://exemplu.test/j?gh_jid=123"),
        (
            "https://exemplu.test/j?utm_source=x&utm_medium=y&utm_campaign=z",
            "https://exemplu.test/j",
        ),
        ("https://exemplu.test/j?a=1&b=2", "https://exemplu.test/j?a=1&b=2"),
        ("https://exemplu.test/j?utmost=1&utm_source=x", "https://exemplu.test/j?utmost=1"),
        ("https://exemplu.test/j?UTM_Source=x", "https://exemplu.test/j"),
        ("https://exemplu.test/j?utm_source=x#sectiune", "https://exemplu.test/j#sectiune"),
        ("https://exemplu.test/j?a=1#sectiune", "https://exemplu.test/j?a=1#sectiune"),
        ("https://exemplu.test/j", "https://exemplu.test/j"),
    ],
)
def test_strip_utm(url, expected):
    assert _strip_utm(url) == expected


# --------------------------------------------------------------------------
# raw_job_from_freehire_doc
# --------------------------------------------------------------------------


def _doc(**over) -> dict:
    doc = {
        "url": "https://exemplu.test/j/1",
        "title": "Dezvoltator Python",
        "company": "Compania Exemplu SRL",
        "cities": ["Cluj-Napoca"],
        "description": "<p>Cerinte</p>",
    }
    doc.update(over)
    return doc


def test_doc_without_url_gives_none():
    doc = _doc()
    del doc["url"]
    assert raw_job_from_freehire_doc(doc, 1000) is None


def test_doc_with_blank_url_gives_none():
    assert raw_job_from_freehire_doc(_doc(url="   "), 1000) is None


def test_closed_doc_gives_none():
    assert raw_job_from_freehire_doc(_doc(closed_at="2026-10-01T00:00:00Z"), 1000) is None


def test_doc_with_null_closed_at_is_kept():
    assert raw_job_from_freehire_doc(_doc(closed_at=None), 1000) is not None


def test_empty_cities_gives_city_none():
    assert raw_job_from_freehire_doc(_doc(cities=[]), 1000).city is None


def test_first_city_is_used():
    job = raw_job_from_freehire_doc(_doc(cities=["Cluj-Napoca", "Bucuresti"]), 1000)
    assert job.city == "Cluj-Napoca"


def test_empty_description_gives_raw_text_none():
    assert raw_job_from_freehire_doc(_doc(description=""), 1000).raw_text is None


def test_missing_description_gives_raw_text_none():
    doc = _doc()
    del doc["description"]
    assert raw_job_from_freehire_doc(doc, 1000).raw_text is None


def test_description_is_converted_to_text():
    job = raw_job_from_freehire_doc(_doc(description="<p>Cerinte</p><p>Python</p>"), 1000)
    assert job.raw_text.splitlines()[0] == "Cerinte"
    assert "<p>" not in job.raw_text


def test_description_respects_max_chars():
    job = raw_job_from_freehire_doc(_doc(description="<p>" + "y" * 300 + "</p>"), 25)
    assert len(job.raw_text) == 25


def test_source_is_freehire_and_remote_is_none():
    job = raw_job_from_freehire_doc(_doc(), 1000)
    assert job.source == "freehire"
    assert job.remote is None


def test_url_is_stripped_of_utm_params():
    job = raw_job_from_freehire_doc(
        _doc(url="https://exemplu.test/j/1?gh_jid=9&utm_source=freehire.me"), 1000
    )
    assert job.url == "https://exemplu.test/j/1?gh_jid=9"


def test_title_and_company_are_normalized():
    job = raw_job_from_freehire_doc(_doc(title="  A &amp;  B ", company="Exemplu  SRL"), 1000)
    assert job.title == "A & B"
    assert job.company == "Exemplu SRL"
