"""Punctul de intrare in linia de comanda.

Trei subcomenzi, in ordinea in care se folosesc:
  harvest  - recolteaza anunturi din surse. Gratuit, nu atinge modelul.
  score    - filtreaza si evalueaza. Singurul pas platit; are --dry-run.
  serve    - porneste aplicatia locala.
"""

from __future__ import annotations

import argparse
import sys


def cmd_harvest(args: argparse.Namespace) -> int:
    raise SystemExit("harvest: neimplementat inca (E3 din plan.md)")


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
