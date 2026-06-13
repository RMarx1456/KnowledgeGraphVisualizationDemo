#!/usr/bin/env python3
"""Wrapper runner: parse CLI arguments and dispatch to the worker modules.

This is the only place with argument-parsing logic. The modules under scripts/
(spacy_extract, visualize, rdf_common) hold the actual functionality as plain,
importable functions and contain no argparse / CLI code of their own.

Commands:
    python cli.py extract <textfile> [--image] [--format svg|png]
        Run spaCy on a text file -> a provenanced Turtle run. With --image, also
        render the graph; the image shares the run's exact filename/provenance.

    python cli.py visualize [selector] [--method M] [--format svg|png]
        Render an existing run to an image. selector: latest (default) | all
        | <run-id> | path/to/run.ttl
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from spacy_extract import run_spacy                          # noqa: E402
from visualize import render, require_tools, resolve_targets  # noqa: E402


def cmd_extract(args: argparse.Namespace) -> None:
    if not args.textfile.exists():
        sys.exit(f"No such file: {args.textfile}")

    ttl = run_spacy(args.textfile)
    print(f"rdf    -> {ttl.relative_to(ROOT)}")

    if args.image:
        require_tools()
        img = render(ttl, args.format)          # same stem as ttl -> same provenance
        print(f"image  -> {img.relative_to(ROOT)}")


def cmd_visualize(args: argparse.Namespace) -> None:
    require_tools()
    for ttl in resolve_targets(args.selector, args.method):
        img = render(ttl, args.format)
        print(f"{ttl.name}  ->  {img.relative_to(ROOT)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Knowledge-graph triple extraction + visualization.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract", help="run spaCy on a text file -> Turtle (+ optional image)")
    e.add_argument("textfile", type=Path, help="input text file")
    e.add_argument("--image", action="store_true",
                   help="also render a graph image (default: off, to save space)")
    e.add_argument("--format", choices=["svg", "png"], default="svg",
                   help="image format when --image is set (default: svg)")
    e.set_defaults(func=cmd_extract)

    v = sub.add_parser("visualize", help="render an existing run to an image")
    v.add_argument("selector", nargs="?", default="latest",
                   help="latest (default) | all | <run-id> | path/to/run.ttl")
    v.add_argument("--method", help="restrict 'latest'/'all' to a method, e.g. spacy")
    v.add_argument("--format", choices=["svg", "png"], default="svg",
                   help="image format (default: svg)")
    v.set_defaults(func=cmd_visualize)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
