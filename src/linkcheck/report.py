"""Render check results as human-readable text or machine-readable JSON."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .checker import LinkResult

__all__ = ["render_json", "render_text", "summarize"]


def summarize(results: list[LinkResult]) -> Counter[str]:
    """Count results by status."""
    return Counter(result.status for result in results)


def render_text(results: list[LinkResult]) -> str:
    """One section per file, then a one-line summary."""
    lines: list[str] = []
    problems = [r for r in results if r.status in ("broken", "error")]
    by_file: dict[Path | None, list[LinkResult]] = {}
    for result in problems:
        by_file.setdefault(result.link.source, []).append(result)

    for source, file_results in by_file.items():
        lines.append(f"{source or '<unknown>'}:")
        for result in file_results:
            lines.append(
                f"  line {result.link.line}: {result.link.url} "
                f"— {result.status}: {result.detail}"
            )
    counts = summarize(results)
    total = len(results)
    lines.append(
        f"{total} link{'s' if total != 1 else ''} checked: "
        f"{counts.get('ok', 0)} ok, {counts.get('broken', 0)} broken, "
        f"{counts.get('error', 0)} errors, {counts.get('skipped', 0)} skipped"
    )
    return "\n".join(lines)


def render_json(results: list[LinkResult]) -> str:
    """A JSON array of result objects, plus a summary object."""
    payload = {
        "results": [
            {
                "file": str(result.link.source) if result.link.source else None,
                "line": result.link.line,
                "url": result.link.url,
                "kind": result.link.kind,
                "status": result.status,
                "detail": result.detail,
            }
            for result in results
        ],
        "summary": dict(summarize(results)),
    }
    return json.dumps(payload, indent=2)
