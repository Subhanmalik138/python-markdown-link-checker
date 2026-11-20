"""Command-line interface for linkcheck.

Usage::

    linkcheck docs/                  # check every Markdown file under docs/
    linkcheck README.md --format json
    linkcheck docs/ --exclude 'localhost|example\\.com' --timeout 5

Exit code is 0 when every checked link is ok (or skipped) and 1 when any
link is broken or errored, so it slots straight into CI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checker import check_links
from .extractor import extract_links
from .report import render_json, render_text, summarize

__all__ = ["main"]

_DEFAULT_EXTENSIONS = (".md", ".markdown")


def _collect_files(paths: list[Path], extensions: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                sorted(p for p in path.rglob("*")
                       if p.is_file() and p.suffix.lower() in extensions)
            )
        else:
            print(f"linkcheck: {path}: no such file or directory", file=sys.stderr)
    return files


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="linkcheck",
        description="Find broken links in Markdown files.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path(".")],
        help="Markdown files or directories to scan (default: current directory)",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text",
        help="report format (default: text)",
    )
    parser.add_argument(
        "--exclude", action="append", default=[],
        metavar="REGEX",
        help="skip links whose URL matches this regex (repeatable)",
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="seconds to wait for each HTTP request (default: 10)",
    )
    parser.add_argument(
        "--max-workers", type=int, default=10,
        help="concurrent HTTP requests (default: 10)",
    )
    parser.add_argument(
        "--extensions", default=",".join(_DEFAULT_EXTENSIONS),
        help="comma-separated file extensions to scan (default: .md,.markdown)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    extensions = tuple(
        ext if ext.startswith(".") else f".{ext}"
        for ext in (e.strip() for e in args.extensions.split(",") if e.strip())
    )
    files = _collect_files(args.paths, extensions)
    if not files:
        print("linkcheck: no Markdown files found", file=sys.stderr)
        return 2

    links = []
    for path in files:
        links.extend(extract_links(path.read_text(errors="replace"), source=path))
    results = check_links(
        links, timeout=args.timeout, max_workers=args.max_workers,
        exclude=args.exclude,
    )

    if args.format == "json":
        print(render_json(results))
    else:
        print(render_text(results))
    counts = summarize(results)
    return 1 if counts.get("broken", 0) + counts.get("error", 0) else 0
