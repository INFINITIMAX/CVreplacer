"""Teste pentru cvreplacer.sources.freehire - fara nicio cerere reala catre retea.

httpx.MockTransport serveste raspunsuri fabricate. Pauzele (time.sleep) sunt inlocuite.
"""

from __future__ import annotations

import httpx
import pytest

from cvreplacer.sources.freehire import harvest, search

BASE_URL = "https://freehire.exemplu.test"
PATH = "/api/v1/agent/jobs/search"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Nicio pauza reala; lista `sleeps` e disponibila testelor care o cer."""
    sleeps: list[float] = []
    monkeypatch.setattr("cvreplacer.sources.freehire.time.sleep", lambda s: sleeps.append(s))
    return sleeps


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)


def _doc(url: str, title: str = "Dezvoltator Python") -> dict:
    return {
        "url": url,
        "title": title,
        "company": "Exemplu SRL",
        "cities": ["Cluj-Napoca"],
        "description": "<p>Descriere</p>",
    }


def _docs(n: int, start: int = 0, prefix: str = "https://exemplu.test/j") -> list[dict]:
    return [_doc(f"{prefix}/{start + i}") for i in range(n)]


def _kwargs(**over) -> dict:
    base = {
        "country": "ro",
        "posted_within_days": 30,
        "max_pages": 5,
        "max_chars": 20000,
    }
    base.update(over)
    return base


def _search(term: str, handler, **over):
    return search(term, client=_client(handler), **_kwargs(**over))


def _harvest(terms, handler, **over):
    return harvest(terms, rate_limit_s=over.pop("rate_limit_s", 0), client=_client(handler),
                   **_kwargs(**over))


# --------------------------------------------------------------------------
# parametrii trimisi
# --------------------------------------------------------------------------


def test_request_sends_expected_path_and_params():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    _search("pgvector", handler, country="ro", posted_within_days=14)

    assert len(seen) == 1
    req = seen[0]
    assert req.url.path == PATH
    params = req.url.params
    assert params["q"] == "pgvector"
    assert params["countries"] == "ro"
    assert params["posted_within_days"] == "14"
    assert params["limit"] == "100"
    assert params["offset"] == "0"


# --------------------------------------------------------------------------
# paginare
# --------------------------------------------------------------------------


def test_stops_after_first_page_when_page_is_shorter_than_100():
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offsets.append(request.url.params["offset"])
        return httpx.Response(200, json={"data": _docs(99), "meta": {"total": 5000}})

    jobs = _search("a", handler)

    assert offsets == ["0"]
    assert len(jobs) == 99


def test_full_page_then_short_page_makes_exactly_two_requests_with_right_offsets():
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(request.url.params["offset"])
        n = 100 if offset == 0 else 40
        return httpx.Response(200, json={"data": _docs(n, start=offset), "meta": {"total": 5000}})

    jobs = _search("a", handler)

    assert offsets == ["0", "100"]
    assert len(jobs) == 140


def test_stops_when_offset_reaches_total_even_if_page_is_full():
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(request.url.params["offset"])
        return httpx.Response(200, json={"data": _docs(100, start=offset), "meta": {"total": 200}})

    jobs = _search("a", handler)

    assert offsets == ["0", "100"], "dupa offset=200 >= total nu mai trebuie nicio cerere"
    assert len(jobs) == 200


def test_stops_at_max_pages_even_if_more_results_exist():
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(request.url.params["offset"])
        return httpx.Response(200, json={"data": _docs(100, start=offset), "meta": {"total": 9999}})

    jobs = _search("a", handler, max_pages=3)

    assert offsets == ["0", "100", "200"]
    assert len(jobs) == 300


def test_missing_total_falls_back_to_short_page_rule():
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(request.url.params["offset"])
        n = 100 if offset == 0 else 3
        return httpx.Response(200, json={"data": _docs(n, start=offset)})

    jobs = _search("a", handler)

    assert offsets == ["0", "100"]
    assert len(jobs) == 103


def test_docs_without_url_or_closed_are_dropped():
    def handler(request: httpx.Request) -> httpx.Response:
        closed = _doc("https://exemplu.test/inchis")
        closed["closed_at"] = "2026-10-01T00:00:00Z"
        no_url = {"title": "fara url"}
        return httpx.Response(
            200, json={"data": [_doc("https://exemplu.test/ok"), closed, no_url], "meta": {}}
        )

    jobs = _search("a", handler)

    assert [j.url for j in jobs] == ["https://exemplu.test/ok"]


# --------------------------------------------------------------------------
# retry
# --------------------------------------------------------------------------


def test_network_error_makes_exactly_two_requests_and_counts_failed():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("nu se conecteaza", request=request)

    result = _harvest(["Python"], handler)

    assert len(calls) == 2
    assert result.n_failed == 1
    assert result.n_queries == 1
    assert result.n_unique == 0


def test_503_makes_exactly_two_requests_and_counts_failed():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503, text="indisponibil")

    result = _harvest(["Python"], handler)

    assert len(calls) == 2
    assert result.n_failed == 1


def test_503_then_200_recovers_and_is_not_counted_failed():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": _docs(2), "meta": {"total": 2}})

    result = _harvest(["Python"], handler)

    assert calls["n"] == 2
    assert result.n_failed == 0
    assert result.n_unique == 2


@pytest.mark.parametrize("status", [400, 404, 429])
def test_4xx_is_not_retried_and_counts_failed(status):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": "x"})

    result = _harvest(["Python"], handler)

    assert len(calls) == 1
    assert result.n_failed == 1


def test_search_propagates_4xx_as_http_status_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(httpx.HTTPStatusError):
        _search("a", handler)


def test_failed_query_does_not_stop_the_others():
    def handler(request: httpx.Request) -> httpx.Response:
        term = request.url.params["q"]
        if term == "rau":
            return httpx.Response(400)
        return httpx.Response(
            200, json={"data": [_doc(f"https://exemplu.test/{term}")], "meta": {"total": 1}}
        )

    result = _harvest(["bun1", "rau", "bun2"], handler)

    assert result.n_queries == 3
    assert result.n_failed == 1
    assert {j.url for j in result.jobs} == {
        "https://exemplu.test/bun1",
        "https://exemplu.test/bun2",
    }


def test_non_json_200_body_counts_as_failed_query_and_run_continues():
    # CAZ DESCHIS (brief E3F): o pagina HTML de mentenanta servita cu 200.
    # Comportamentul dorit: interogarea e numarata ca esuata, restul merg mai departe.
    # Banuiala: response.json() arunca ValueError (nu httpx.HTTPError) si opreste tot harvest.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "mentenanta":
            return httpx.Response(200, text="<html><body>In mentenanta</body></html>")
        return httpx.Response(
            200, json={"data": [_doc("https://exemplu.test/ok")], "meta": {"total": 1}}
        )

    result = _harvest(["mentenanta", "normal"], handler)

    assert result.n_failed == 1
    assert [j.url for j in result.jobs] == ["https://exemplu.test/ok"]


@pytest.mark.parametrize("body", [[], "text", 42])
def test_valid_json_that_is_not_an_object_counts_as_failed_query(body):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "ciudat":
            return httpx.Response(200, json=body)
        return httpx.Response(
            200, json={"data": [_doc("https://exemplu.test/ok")], "meta": {"total": 1}}
        )

    result = _harvest(["ciudat", "normal"], handler)

    assert result.n_failed == 1
    assert [j.url for j in result.jobs] == ["https://exemplu.test/ok"]


def test_null_data_and_non_dict_items_are_skipped_not_fatal():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "gol":
            return httpx.Response(200, json={"data": None, "meta": {"total": 0}})
        return httpx.Response(
            200, json={"data": ["nu-e-dict", _doc("https://exemplu.test/ok")], "meta": {"total": 2}}
        )

    result = _harvest(["gol", "amestec"], handler)

    assert result.n_failed == 0
    assert [j.url for j in result.jobs] == ["https://exemplu.test/ok"]


# --------------------------------------------------------------------------
# unificare pe url
# --------------------------------------------------------------------------


def test_same_url_across_queries_counted_raw_twice_unique_once():
    def handler(request: httpx.Request) -> httpx.Response:
        term = request.url.params["q"]
        docs = [_doc("https://exemplu.test/comun")]
        if term == "b":
            docs.append(_doc("https://exemplu.test/doar-b"))
        return httpx.Response(200, json={"data": docs, "meta": {"total": len(docs)}})

    result = _harvest(["a", "b"], handler)

    assert result.n_queries == 2
    assert result.n_raw == 3
    assert result.n_unique == 2
    assert [j.url for j in result.jobs] == [
        "https://exemplu.test/comun",
        "https://exemplu.test/doar-b",
    ]


def test_empty_terms_are_skipped():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    result = _harvest(["", "a", ""], handler)

    assert len(calls) == 1
    assert result.n_queries == 1


# --------------------------------------------------------------------------
# pauze
# --------------------------------------------------------------------------


def test_sleeps_between_pages_of_the_same_query(no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json={"data": _docs(100, start=offset), "meta": {"total": 9999}})

    _harvest(["a"], handler, rate_limit_s=0.7, max_pages=3)

    assert no_sleep == [0.7, 0.7], "3 pagini -> 2 pauze intre pagini, nimic dupa ultima"


def test_sleeps_between_queries_not_after_the_last(no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    _harvest(["a", "b", "c"], handler, rate_limit_s=1.5)

    assert no_sleep == [1.5, 1.5]


def test_no_sleep_for_single_query_single_page(no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "meta": {"total": 0}})

    _harvest(["a"], handler, rate_limit_s=1.5)

    assert no_sleep == []


def test_pages_and_queries_both_sleep(no_sleep):
    # 2 interogari x 2 pagini: pauza intre pagini (x2) + pauza intre interogari (x1)
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json={"data": _docs(100, start=offset), "meta": {"total": 9999}})

    _harvest(["a", "b"], handler, rate_limit_s=0.7, max_pages=2)

    assert no_sleep == [0.7, 0.7, 0.7]


# --------------------------------------------------------------------------
# configurare
# --------------------------------------------------------------------------


def test_harvest_without_client_or_base_url_raises_value_error():
    with pytest.raises(ValueError):
        harvest(["a"], rate_limit_s=0, base_url=None, user_agent=None, **_kwargs())
