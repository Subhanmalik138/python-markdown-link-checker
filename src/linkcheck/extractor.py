"""Extract links from Markdown text, ignoring code.

Recognised forms (all with 1-based line numbers):

* inline links ``[text](url)`` and images ``![alt](url)`` (optional title
  and ``<url>`` destinations supported),
* reference links ``[text][ref]``, ``[text][]`` and shortcut ``[text]``,
  resolved against ``[ref]: url`` definitions anywhere in the document,
* autolinks ``<https://example.com>``,
* bare ``https://...`` URLs in prose.

Fenced code blocks and inline code spans are masked out before scanning,
so links inside examples are never reported. Masking replaces characters
with spaces while preserving newlines, so line numbers stay exact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Link", "extract_links"]

_FENCED_BLOCK = re.compile(r"(?ms)^[ \t]{0,3}(```|~~~)[^\n]*\n.*?\n[ \t]{0,3}\1[ \t]*$")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_REF_DEF = re.compile(r"(?m)^[ \t]{0,3}\[([^\]]+)\]:[ \t]*<?([^>\s]+)>?")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*(?:<([^>]*)>|([^\s)]+))(?:\s+\"[^\"]*\")?\s*\)")
_INLINE_LINK = re.compile(r"\[([^\]]*)\]\(\s*(?:<([^>]*)>|([^\s)]+))(?:\s+\"[^\"]*\")?\s*\)")
_FULL_REF = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
_SHORTCUT_REF = re.compile(r"\[([^\]]+)\](?![\(\[:])")
_AUTOLINK = re.compile(r"<([a-zA-Z][a-zA-Z0-9.+-]*:[^>\s]+)>")
_BARE_URL = re.compile(r"https?://[^\s<>\]\)\"']+")

_TRAILING_PUNCT = ".,;:!?)"


@dataclass(frozen=True)
class Link:
    """One link found in a Markdown document."""

    url: str
    line: int  # 1-based line number in the source file
    kind: str  # "link" or "image"
    text: str = ""
    source: Path | None = None


def _mask(text: str, pattern: re.Pattern[str]) -> str:
    """Replace every match of *pattern* with spaces, keeping newlines."""

    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    return pattern.sub(blank, text)


def _normalize_ref(ref: str) -> str:
    return " ".join(ref.split()).lower()


def _line_no(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def extract_links(text: str, source: Path | None = None) -> list[Link]:
    """Return every link in *text*, in document order."""
    # Code is not prose: mask it out first, preserving line numbers.
    masked = _mask(text, _FENCED_BLOCK)
    masked = _mask(masked, _INLINE_CODE)

    links: list[tuple[int, Link]] = []
    # Working copy: each found link is blanked so later passes (especially
    # the bare-URL pass) cannot match inside an already-found link.
    work = masked

    def take(match: re.Match[str], kind: str) -> Link:
        url = match.group(2) or match.group(3)
        return Link(
            url=url.strip(),
            line=_line_no(masked, match.start()),
            kind=kind,
            text=match.group(1),
            source=source,
        )

    # Reference definitions: collected first, never reported as links.
    definitions: dict[str, str] = {}
    for match in _REF_DEF.finditer(masked):
        definitions.setdefault(_normalize_ref(match.group(1)), match.group(2))
    work = _mask(work, _REF_DEF)

    for pattern, kind in ((_IMAGE, "image"), (_INLINE_LINK, "link")):
        for match in pattern.finditer(work):
            links.append((match.start(), take(match, kind)))
        work = _mask(work, pattern)

    for match in _FULL_REF.finditer(work):
        ref = match.group(2) or match.group(1)
        url = definitions.get(_normalize_ref(ref))
        if url is not None:
            links.append((match.start(), Link(
                url=url, line=_line_no(masked, match.start()),
                kind="link", text=match.group(1), source=source,
            )))
    work = _mask(work, _FULL_REF)

    for match in _SHORTCUT_REF.finditer(work):
        url = definitions.get(_normalize_ref(match.group(1)))
        if url is not None:
            links.append((match.start(), Link(
                url=url, line=_line_no(masked, match.start()),
                kind="link", text=match.group(1), source=source,
            )))
    work = _mask(work, _SHORTCUT_REF)

    for match in _AUTOLINK.finditer(work):
        links.append((match.start(), Link(
            url=match.group(1), line=_line_no(masked, match.start()),
            kind="link", source=source,
        )))
    work = _mask(work, _AUTOLINK)

    for match in _BARE_URL.finditer(work):
        url = match.group(0).rstrip(_TRAILING_PUNCT)
        links.append((match.start(), Link(
            url=url, line=_line_no(masked, match.start()),
            kind="link", source=source,
        )))

    # Document order, not pass order: a reference link before an inline
    # link on the same line must still come first.
    links.sort(key=lambda item: item[0])
    return [link for _, link in links]
