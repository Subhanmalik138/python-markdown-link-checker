"""Anchor (``#fragment``) collection with GitHub-style heading slugs.

GitHub renders a heading ``## Hello, World!`` as the anchor
``#hello-world``: lower-cased, punctuation stripped, spaces turned into
hyphens. Repeated headings get ``-1``, ``-2`` suffixes, exactly as GitHub
does. Explicit ``<a id="...">`` / ``<a name="...">`` anchors are collected
as well, and so are Setext (``===`` / ``---``) headings.
"""

from __future__ import annotations

import re
from collections import Counter

__all__ = ["collect_anchors", "slugify"]

_ATX_HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$")
_SETEXT_HEADING = re.compile(r"(?m)^(.+)\n[ \t]{0,3}(=+|-+)[ \t]*$")
_HTML_ANCHOR = re.compile(r'<a\s[^>]*\b(?:id|name)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_PUNCT = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_FENCED_BLOCK = re.compile(r"(?ms)^[ \t]{0,3}(```|~~~)[^\n]*\n.*?\n[ \t]{0,3}\1[ \t]*$")


def slugify(heading: str) -> str:
    """Turn a heading into its GitHub-style anchor slug."""
    text = heading.strip().lower()
    text = _PUNCT.sub("", text)  # strip punctuation, keep letters/digits/_/-
    text = _SPACES.sub("-", text.strip())  # spaces (and runs) -> one hyphen
    return text.strip("-")


def collect_anchors(markdown: str) -> set[str]:
    """Return every anchor a Markdown document defines.

    Includes heading slugs (with GitHub's ``-1``/``-2`` dedup suffixes for
    repeated headings) and explicit HTML ``id``/``name`` anchors.
    """
    headings: list[str] = []
    # Headings inside fenced code blocks are examples, not real headings.
    markdown = _FENCED_BLOCK.sub("", markdown)
    for match in _ATX_HEADING.finditer(markdown):
        headings.append(match.group(1))
    for match in _SETEXT_HEADING.finditer(markdown):
        headings.append(match.group(1))

    anchors: set[str] = set()
    seen: Counter[str] = Counter()
    for heading in headings:
        slug = slugify(heading)
        if not slug:
            continue
        seen[slug] += 1
        anchors.add(slug if seen[slug] == 1 else f"{slug}-{seen[slug] - 1}")
    for match in _HTML_ANCHOR.finditer(markdown):
        anchors.add(match.group(1))
    return anchors
