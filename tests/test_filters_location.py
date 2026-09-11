"""Teste pentru filters.location — oras de domiciliu si mod de lucru.

Tabelul din docs/handoff/E3-E4-tester.md e sursa fiecarui caz de mai jos;
scurgerile pe care planner-ul le-a gasit deja (city=None, city="all") trebuie
blocate definitiv aici.
"""

from __future__ import annotations

from conftest import make_job_row

from cvreplacer.config import LocationConfig
from cvreplacer.filters.location import make_location_filter

_DEFAULT_CONFIG = LocationConfig(
    home_city="Bucuresti",
    accept_remote=True,
    accept_hybrid_home_only=True,
    extra_cities=[],
)


def _apply(jobs, config=_DEFAULT_CONFIG):
    step = make_location_filter(config)
    return step.fn(jobs)


def _kept(job, config=_DEFAULT_CONFIG) -> bool:
    return job.url in {j.url for j in _apply([job], config)}


def test_city_none_passes_regardless_of_remote_mode():
    job = make_job_row(city=None, remote="on-site")
    assert _kept(job)


def test_city_all_passes():
    job = make_job_row(city="all", remote="on-site")
    assert _kept(job)


def test_home_city_on_site_passes():
    job = make_job_row(city="Bucuresti", remote="on-site")
    assert _kept(job)


def test_home_city_with_diacritics_passes():
    job = make_job_row(city="București", remote="on-site")
    assert _kept(job)


def test_home_city_uppercase_passes():
    job = make_job_row(city="BUCURESTI", remote="on-site")
    assert _kept(job)


def test_other_city_on_site_is_cut():
    job = make_job_row(city="Iasi", remote="on-site")
    assert not _kept(job)


def test_city_list_containing_home_city_passes():
    job = make_job_row(city="Iasi,Targu-Mures,Bucuresti", remote="on-site")
    assert _kept(job)


def test_remote_from_another_city_passes():
    job = make_job_row(city="Iasi", remote="remote")
    assert _kept(job)


def test_remote_mode_none_passes():
    job = make_job_row(city="Iasi", remote=None)
    assert _kept(job)


def test_hybrid_at_home_city_passes():
    job = make_job_row(city="Bucuresti", remote="hybrid")
    assert _kept(job)


def test_hybrid_at_another_city_is_cut():
    job = make_job_row(city="Iasi", remote="hybrid")
    assert not _kept(job)


# --------------------------------------------------------------------------
# configurare: accept_remote, accept_hybrid_home_only, extra_cities
# --------------------------------------------------------------------------


def test_remote_cut_when_accept_remote_disabled():
    config = LocationConfig(
        home_city="Bucuresti", accept_remote=False, accept_hybrid_home_only=True, extra_cities=[]
    )
    job = make_job_row(city="Iasi", remote="remote")
    assert not _kept(job, config)


def test_hybrid_anywhere_when_accept_hybrid_home_only_disabled():
    config = LocationConfig(
        home_city="Bucuresti", accept_remote=True, accept_hybrid_home_only=False, extra_cities=[]
    )
    job = make_job_row(city="Iasi", remote="hybrid")
    assert _kept(job, config)


def test_extra_cities_allow_on_site_match():
    config = LocationConfig(
        home_city="Bucuresti",
        accept_remote=True,
        accept_hybrid_home_only=True,
        extra_cities=["Cluj-Napoca"],
    )
    job = make_job_row(city="Cluj-Napoca", remote="on-site")
    assert _kept(job, config)


def test_extra_cities_do_not_allow_unrelated_city():
    config = LocationConfig(
        home_city="Bucuresti",
        accept_remote=True,
        accept_hybrid_home_only=True,
        extra_cities=["Cluj-Napoca"],
    )
    job = make_job_row(city="Iasi", remote="on-site")
    assert not _kept(job, config)
