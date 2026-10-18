"""Punctul de intrare in linia de comanda.

Subcomenzi, in ordinea in care se folosesc:
  harvest  - recolteaza anunturi din surse. Gratuit, nu atinge modelul.
  fetch    - descarca descrierea pentru supravietuitorii filtrelor ieftine.
  score    - filtreaza si evalueaza. Singurul pas platit; are --dry-run.
  serve    - porneste aplicatia locala.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime

from cvreplacer import fetch, storage
from cvreplacer.config import (
    load_company_cap_config,
    load_fetch_config,
    load_freehire_config,
    load_harvest_config,
    load_location_config,
)
from cvreplacer.filters import apply_chain
from cvreplacer.filters.company_cap import make_company_cap_filter
from cvreplacer.filters.dedup import make_dedup_filter
from cvreplacer.filters.location import make_location_filter
from cvreplacer.sources import freehire, peviitor, queries
from cvreplacer.sources.peviitor import HarvestResult
from cvreplacer.storage.models import JobRow, RawJob

_PROFILE_PATH = "data/cv/profile.json"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_harvest(args: argparse.Namespace) -> int:
    # sursa manual e lipita din interfata (E7), nu din aceasta comanda -
    # harvest recolteaza automat doar din peViitor si freehire.
    wanted = ["peviitor", "freehire"] if args.source == "all" else [args.source]

    config = load_harvest_config()
    profile = queries.load_profile(_PROFILE_PATH)
    terms = queries.build_queries(profile)

    conn = storage.connect(config.db_path)
    run_id = storage.start_run(conn)

    results: dict[str, HarvestResult] = {}
    if "peviitor" in wanted:
        results["peviitor"] = peviitor.harvest(
            terms,
            rate_limit_s=config.rate_limit_s,
            base_url=config.peviitor_base,
            user_agent=config.user_agent,
        )
    if "freehire" in wanted:
        freehire_config = load_freehire_config()
        results["freehire"] = freehire.harvest(
            terms,
            rate_limit_s=config.rate_limit_s,
            base_url=freehire_config.base,
            user_agent=config.user_agent,
            country=freehire_config.country,
            posted_within_days=freehire_config.posted_within_days,
            max_pages=freehire_config.max_pages,
            max_chars=load_fetch_config().max_description_chars,
        )

    # unificare pe url: la conflict castiga prima sursa (ordinea din `results`)
    merged: dict[str, RawJob] = {}
    for result in results.values():
        for job in result.jobs:
            merged.setdefault(job.url, job)
    jobs = list(merged.values())

    # o sursa cu toate interogarile esuate nu spune nimic despre anunturile ei
    ok_sources = {
        name for name, r in results.items() if not (r.n_queries > 0 and r.n_failed == r.n_queries)
    }

    run_at = _now_iso()
    seen = storage.upsert_seen(conn, jobs, run_at)
    dead = storage.mark_absent(conn, set(merged), run_at, sources=ok_sources)

    n_queries = sum(r.n_queries for r in results.values())
    n_raw = sum(r.n_raw for r in results.values())
    n_failed = sum(r.n_failed for r in results.values())
    storage.finish_run(
        conn,
        run_id,
        n_harvested=n_raw,
        notes=f"interogari={n_queries} esuate={n_failed}",
    )

    print(f"interogari: {n_queries}")
    print(f"brut: {n_raw}")
    print(f"unic: {len(jobs)}")
    print(f"esuate: {n_failed}")
    for name, r in results.items():
        print(f"  {name}: {r.n_raw}/{r.n_unique}/{r.n_failed}")
    print(f"noi: {seen.new}")
    print(f"reinviate: {seen.revived}")
    print(f"marcate moarte: {dead}")
    return 0


def _needs_download(job: JobRow) -> bool:
    """False pentru anunturile al caror text a venit deja din sursa."""
    return job.fetch_status != "source"


def cmd_fetch(args: argparse.Namespace) -> int:
    start = time.monotonic()

    harvest_config = load_harvest_config()
    fetch_config = load_fetch_config()
    location_config = load_location_config()
    company_cap_config = load_company_cap_config()

    conn = storage.connect(harvest_config.db_path)
    jobs = storage.list_active_jobs(conn)

    # "seen" nu ruleaza aici: depinde de un prompt_version de scoring, care
    # nu exista inca (E6 neimplementat). "years" ruleaza dupa fetch, pe
    # raw_text, nu pe metadate - de asta nu e in acest lant (spec.md R6, R7).
    survivors, reports = apply_chain(
        jobs,
        [
            make_location_filter(location_config),
            make_dedup_filter(),
            make_company_cap_filter(company_cap_config),
        ],
    )

    if args.limit is not None:
        survivors = survivors[: args.limit]

    urls = [job.url for job in survivors if _needs_download(job)]
    n_from_source = len(survivors) - len(urls)
    results = fetch.fetch_many(urls, fetch_config, force=args.force)

    n_from_cache = sum(1 for r in results if r.from_cache)
    n_downloaded = len(results) - n_from_cache
    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.fetch_status] = status_counts.get(r.fetch_status, 0) + 1

    for result in results:
        storage.save_fetch_result(
            conn,
            result.url,
            raw_text=result.raw_text,
            fetch_status=result.fetch_status,
            fetched_at=result.fetched_at,
        )

    duration_s = time.monotonic() - start

    for report in reports:
        print(f"filtru {report.name}: {report.n_in} -> {report.n_out} (taiate: {report.n_cut})")
    print(f"candidati dupa filtre: {len(survivors)}")
    print(f"din sursa: {n_from_source}")
    print(f"din cache: {n_from_cache}")
    print(f"descarcati: {n_downloaded}")
    for status in sorted(status_counts):
        count = status_counts[status]
        pct = 100 * count / len(results) if results else 0.0
        print(f"  {status}: {count} ({pct:.1f}%)")
    print(f"durata: {duration_s:.1f}s")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    if args.dry_run:
        raise SystemExit("score --dry-run: neimplementat inca (E6 din plan.md)")
    raise SystemExit("score: neimplementat inca (E6 din plan.md)")


def cmd_serve(args: argparse.Namespace) -> int:
    raise SystemExit("serve: neimplementat inca (E7 din plan.md)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cvreplacer",
        description="Potriveste anunturi de job cu CV-ul tau, local.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_harvest = sub.add_parser("harvest", help="recolteaza anunturi din surse (gratuit)")
    p_harvest.add_argument(
        "--source",
        default="all",
        choices=["peviitor", "freehire", "all"],
        help="peviitor | freehire | all",
    )
    p_harvest.set_defaults(func=cmd_harvest)

    p_fetch = sub.add_parser("fetch", help="descarca descrierile pentru supravietuitorii filtrelor")
    p_fetch.add_argument("--limit", type=int, default=None, help="plafon peste candidatii filtrati")
    p_fetch.add_argument("--force", action="store_true", help="ignora cache-ul, redescarca tot")
    p_fetch.set_defaults(func=cmd_fetch)

    p_score = sub.add_parser("score", help="filtreaza si evalueaza anunturile")
    p_score.add_argument(
        "--dry-run",
        action="store_true",
        help="numara ce ar fi trimis si estimeaza costul, fara sa trimita nimic",
    )
    p_score.add_argument("--limit", type=int, default=None, help="plafon peste cel din .env")
    p_score.set_defaults(func=cmd_score)

    p_serve = sub.add_parser("serve", help="porneste aplicatia locala")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
