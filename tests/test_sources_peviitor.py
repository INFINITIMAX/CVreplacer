"""Teste pentru cvreplacer.sources.peviitor — fara nicio cerere reala catre retea.

httpx.MockTransport serveste raspunsuri fabricate; niciun test nu atinge internetul.
"""

from __future__ import annotations

import httpx
import pytest

from cvreplacer.sources.peviitor import HarvestResult, harvest, search

BASE_URL = "https://peviitor.exemplu.test"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)


def _doc(url: str, title: str = "Python Developer") -> dict:
    return {"url": url, "title": title, "company": "Exemplu SRL"}


# --------------------------------------------------------------------------
# 404 cu "No jobs found" = zero rezultate, nu esec
# --------------------------------------------------------------------------


def test_404_no_jobs_found_returns_empty_list_not_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "No jobs found"})

    client = _client(handler)
    result = search("pgvector", client=client)
    assert result == []


def test_200_with_docs_returns_jobs():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"docs": [_doc("https://exemplu.test/1")]}})

    client = _client(handler)
    result = search("Python", client=client)
    assert len(result) == 1
    assert result[0].url == "https://exemplu.test/1"


def test_other_http_error_status_raises():
    # o eroare 500 reala nu trebuie confundata cu "zero rezultate" - trebuie sa se propage,
    # altfel _search_with_retry / harvest nu ar mai numara-o ca esec.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        search("Python", client=client)


# --------------------------------------------------------------------------
# reincercare la eroare de retea
# --------------------------------------------------------------------------


def test_network_error_retried_once_then_counted_as_failed():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("nu se conecteaza", request=request)

    client = _client(handler)
    result = harvest(["Python"], rate_limit_s=0, client=client)

    assert len(calls) == 2, "trebuie o reincercare, nu mai multe si nu zero"
    assert result.n_failed == 1
    assert result.n_raw == 0
    assert result.n_unique == 0


def test_network_error_recovers_on_retry_counts_as_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("nu se conecteaza", request=request)
        return httpx.Response(200, json={"response": {"docs": [_doc("https://exemplu.test/1")]}})

    client = _client(handler)
    result = harvest(["Python"], rate_limit_s=0, client=client)

    assert calls["n"] == 2
    assert result.n_failed == 0
    assert result.n_unique == 1


# --------------------------------------------------------------------------
# unificare pe url peste mai multe interogari
# --------------------------------------------------------------------------


def test_same_url_from_multiple_terms_counted_once():
    def handler(request: httpx.Request) -> httpx.Response:
        # acelasi anunt, indiferent de termenul cautat
        return httpx.Response(
            200, json={"response": {"docs": [_doc("https://exemplu.test/1")]}}
        )

    client = _client(handler)
    result = harvest(["Python", "Django", "FastAPI"], rate_limit_s=0, client=client)

    assert result.n_queries == 3
    assert result.n_raw == 3
    assert result.n_unique == 1
    assert len(result.jobs) == 1


def test_different_urls_across_terms_all_kept():
    def handler(request: httpx.Request) -> httpx.Response:
        term = request.url.params.get("q")
        return httpx.Response(
            200, json={"response": {"docs": [_doc(f"https://exemplu.test/{term}")]}}
        )

    client = _client(handler)
    result = harvest(["Python", "Django"], rate_limit_s=0, client=client)

    assert result.n_unique == 2
    assert {job.url for job in result.jobs} == {
        "https://exemplu.test/Python",
        "https://exemplu.test/Django",
    }


# --------------------------------------------------------------------------
# HarvestResult raporteaza corect intr-un scenariu mixt
# --------------------------------------------------------------------------


def test_harvest_result_counts_mixed_scenario_correctly():
    # "found" -> 2 docs; "empty" -> 404 zero rezultate; "broken" -> eroare persistenta
    def handler(request: httpx.Request) -> httpx.Response:
        term = request.url.params.get("q")
        if term == "found":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "docs": [_doc("https://exemplu.test/a"), _doc("https://exemplu.test/b")]
                    }
                },
            )
        if term == "empty":
            return httpx.Response(404, json={"error": "No jobs found"})
        raise httpx.ConnectError("nu se conecteaza", request=request)

    client = _client(handler)
    result = harvest(["found", "empty", "broken"], rate_limit_s=0, client=client)

    assert isinstance(result, HarvestResult)
    assert result.n_queries == 3
    assert result.n_raw == 2
    assert result.n_unique == 2
    assert result.n_failed == 1


# --------------------------------------------------------------------------
# pauza intre cereri (ceas fals, fara sleep real)
# --------------------------------------------------------------------------


def test_rate_limit_sleeps_between_queries_not_after_last(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("cvreplacer.sources.peviitor.time.sleep", lambda s: sleeps.append(s))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"docs": []}})

    client = _client(handler)
    harvest(["a", "b", "c"], rate_limit_s=2.5, client=client)

    assert sleeps == [2.5, 2.5], "pauza intre 3 interogari: de doua ori, niciodata dupa ultima"


def test_rate_limit_not_called_for_single_query(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("cvreplacer.sources.peviitor.time.sleep", lambda s: sleeps.append(s))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"docs": []}})

    client = _client(handler)
    harvest(["a"], rate_limit_s=2.5, client=client)

    assert sleeps == []


# --------------------------------------------------------------------------
# validare configurare fara client injectat
# --------------------------------------------------------------------------


def test_harvest_without_client_or_base_url_raises_value_error():
    with pytest.raises(ValueError):
        harvest(["Python"], rate_limit_s=0, base_url=None, user_agent=None)
