"""Punctul de intrare in linia de comanda.

Trei subcomenzi, in ordinea in care se folosesc:
  harvest  - recolteaza anunturi din surse. Gratuit, nu atinge modelul.
  score    - filtreaza si evalueaza. Singurul pas platit; are --dry-run.
  serve    - porneste aplicatia locala.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from cvreplacer import storage
from cvreplacer.config import load_harvest_config
from cvreplacer.sources import peviitor, queries

_PROFILE_PATH = "data/cv/profile.json"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_harvest(args: argparse.Namespace) -> int:
    # sursa manual e lipita din interfata (E7), nu din aceasta comanda -
    # harvest recolteaza automat doar din peViitor.
    del args

    config = load_harvest_config()
    profile = queries.load_profile(_PROFILE_PATH)
    terms = queries.build_queries(profile)

    conn = storage.connect(config.db_path)
    run_id = storage.start_run(conn)

    result = peviitor.harvest(
        terms,
        rate_limit_s=config.rate_limit_s,
        base_url=config.peviitor_base,
        user_agent=config.user_agent,
    )

    run_at = _now_iso()
    seen = storage.upsert_seen(conn, result.jobs, run_at)
    dead = storage.mark_absent(conn, {job.url for job in result.jobs}, run_at)
    storage.finish_run(
        conn,
        run_id,
        n_harvested=result.n_raw,
        notes=f"interogari={result.n_queries} esuate={result.n_failed}",
    )

    print(f"interogari: {result.n_queries}")
    print(f"brut: {result.n_raw}")
    print(f"unic: {result.n_unique}")
    print(f"esuate: {result.n_failed}")
    print(f"noi: {seen.new}")
    print(f"reinviate: {seen.revived}")
    print(f"marcate moarte: {dead}")
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
    p_harvest.add_argument("--source", default="all", help="peviitor | manual | all")
    p_harvest.set_defaults(func=cmd_harvest)

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
