"""Teste pentru cvreplacer.sources.manual — lipirea manuala a unui anunt."""

from __future__ import annotations

import pytest

from cvreplacer.sources.manual import from_pasted_text


def test_pasted_text_extracts_title_and_company_from_first_two_lines():
    text = "Python Developer\nExemplu SRL\nRestul descrierii aici."
    job = from_pasted_text("https://exemplu.test/anunt", text)

    assert job.source == "manual"
    assert job.title == "Python Developer"
    assert job.company == "Exemplu SRL"
    assert job.raw_text == text
    assert job.url == "https://exemplu.test/anunt"
    assert job.city is None
    assert job.remote is None


def test_pasted_text_with_single_line_leaves_company_empty():
    job = from_pasted_text("https://exemplu.test/anunt", "Doar un titlu")
    assert job.title == "Doar un titlu"
    assert job.company == ""


def test_pasted_text_blank_leaves_title_and_company_empty_no_invention():
    job = from_pasted_text("https://exemplu.test/anunt", "\n\n   \n")
    assert job.title == ""
    assert job.company == ""


def test_pasted_text_empty_string_leaves_title_and_company_empty():
    job = from_pasted_text("https://exemplu.test/anunt", "")
    assert job.title == ""
    assert job.company == ""
    assert job.raw_text == ""


def test_title_and_company_lines_are_normalized():
    text = "Python  &amp;  Django  Developer\n  Exemplu   SRL  "
    job = from_pasted_text("https://exemplu.test/anunt", text)
    assert job.title == "Python & Django Developer"
    assert job.company == "Exemplu SRL"


def test_skips_blank_lines_before_title_and_company():
    text = "\n\nPython Developer\n\nExemplu SRL"
    job = from_pasted_text("https://exemplu.test/anunt", text)
    assert job.title == "Python Developer"
    assert job.company == "Exemplu SRL"


def test_missing_url_raises_value_error():
    with pytest.raises(ValueError):
        from_pasted_text("", "Python Developer\nExemplu SRL")


def test_blank_url_raises_value_error():
    with pytest.raises(ValueError):
        from_pasted_text("   ", "Python Developer\nExemplu SRL")


def test_url_is_stripped():
    job = from_pasted_text("  https://exemplu.test/anunt  ", "Titlu\nCompanie")
    assert job.url == "https://exemplu.test/anunt"
