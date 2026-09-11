"""Teste pentru cvreplacer.sources.queries — generarea interogarilor din profil.

Niciun termen real din profilul lui Lucian nu trebuie sa apara aici: profilurile
sunt fabricate, minimale, ca sa dovedeasca ca termenii vin din profil, nu din cod.
"""

from __future__ import annotations

from cvreplacer.sources.queries import MAX_QUERIES, build_queries


def _skill(name: str) -> dict:
    return {"name": name}


def _profile(skills=None, headline=None, experience=None, domain=None) -> dict:
    profile: dict = {"cv": {}}
    if skills is not None:
        profile["cv"]["skills"] = skills
    if experience is not None:
        profile["cv"]["experience"] = experience
    if domain is not None:
        profile["cv"]["domain_knowledge"] = domain
    if headline is not None:
        profile["identity"] = {"headline": headline}
    return profile


# --------------------------------------------------------------------------
# un profil fals, minimal, diferit de profilul real
# --------------------------------------------------------------------------


def test_fake_profile_produces_only_its_own_terms():
    profile = _profile(
        skills=[_skill("Cobol"), _skill("Fortran")],
        headline="Sudor",
        domain=[{"name": "Metalurgie"}],
    )
    queries = build_queries(profile)

    assert set(queries) == {"Cobol", "Fortran", "Sudor", "Metalurgie"}
    # niciun termen din profilul real (Python/AI/etc.) nu apare - daca apare,
    # termenii sunt codificati in sursa, nu extrasi din profil.
    assert "Python" not in queries
    assert "AI Engineer" not in queries


def test_empty_profile_does_not_crash_and_returns_empty_list():
    assert build_queries({}) == []


def test_profile_with_missing_cv_section_does_not_crash():
    assert build_queries({"identity": {"headline": "Sudor"}}) == ["Sudor"]


def test_profile_with_empty_lists_does_not_crash():
    profile = _profile(skills=[], experience=[], domain=[])
    assert build_queries(profile) == []


# --------------------------------------------------------------------------
# limita si deduplicarea
# --------------------------------------------------------------------------


def test_at_most_max_queries_returned():
    skills = [_skill(f"Skill{i}") for i in range(50)]
    queries = build_queries(_profile(skills=skills))
    assert len(queries) == MAX_QUERIES


def test_queries_are_deduplicated_case_insensitively():
    skills = [_skill("Cobol"), _skill("cobol"), _skill("COBOL ")]
    queries = build_queries(_profile(skills=skills))
    assert queries.count("Cobol") == 1
    assert len(queries) == 1


def test_skills_longer_than_two_words_are_excluded():
    skills = [_skill("cost and token budgeting"), _skill("Cobol")]
    queries = build_queries(_profile(skills=skills))
    assert "cost and token budgeting" not in queries
    assert "Cobol" in queries


def test_skill_without_name_is_skipped_not_crashed():
    skills = [{"nume_gresit": "Cobol"}, _skill("Fortran")]
    queries = build_queries(_profile(skills=skills))
    assert queries == ["Fortran"]


# --------------------------------------------------------------------------
# titluri de rol RO/EN
# --------------------------------------------------------------------------


def test_role_title_with_known_type_adds_translated_variant():
    profile = _profile(headline="AI Engineer")
    queries = build_queries(profile)
    assert "AI Engineer" in queries
    assert "inginer AI" in queries


def test_role_title_with_unknown_type_only_adds_original():
    profile = _profile(headline="Titlu Straniu Wizard")
    queries = build_queries(profile)
    assert "Titlu Straniu Wizard" in queries
    assert not any("wizard" in q.lower() for q in queries if q != "Titlu Straniu Wizard")


def test_single_word_role_not_translated():
    profile = _profile(headline="Manager")
    queries = build_queries(profile)
    assert queries == ["Manager"]


def test_experience_roles_included_alongside_headline():
    profile = _profile(
        headline="Backend Developer",
        experience=[{"role": "Data Analyst"}],
    )
    queries = build_queries(profile)
    assert "Backend Developer" in queries
    assert "Data Analyst" in queries
    assert "analist Data" in queries
