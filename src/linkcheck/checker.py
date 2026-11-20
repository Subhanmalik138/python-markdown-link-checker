"""Verify extracted links.

Three kinds of links, three kinds of checks:

* ``http(s)://`` — fetched concurrently with a thread pool. A ``HEAD``
  request is tried first; servers that refuse it (405/501) get a ``GET``.
  2xx/3xx is ok, 4xx/5xx is broken, and anything that stops the request
  (DNS failure, timeout, TLS error) is an ``error`` rather than a
  judgement about the link itself.
* relative paths / ``#anchors`` — resolved against the filesystem
  relative to the file the link came from; fragments are checked against
  the target document's heading slugs (see :mod:`linkcheck.anchors`).
* anything else (``mailto:``, ``tel:``, ``ftp:``, ``data:`` …) — skipped;
  this tool checks links, it does not validate email addresses.

Repeated URLs are fetched once and the result reused, and anchor sets
are cached per file so a document linked from many places is parsed once.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .anchors import collect_anchors
from .extractor import Link

__all__ = ["LinkResult", "check_links"]

_USER_AGENT = "linkcheck/1.0 (+https://github.com/Subhanmalik138/python-markdown-link-checker)"


@dataclass(frozen=True)
class LinkResult:
    """The verdict for one extracted link."""

    link: Link
    status: str  # "ok" | "broken" | "error" | "skipped"
    detail: str = ""
    checked_url: str = ""


def _fetch(url: str, timeout: float) -> tuple[str, str] | None:
    """One HTTP check; returns None when the caller should retry with GET."""
    request = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ("ok", f"HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        if exc.code in (405, 501):
            return None  # HEAD not allowed; caller retries with GET
        return ("broken", f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return ("error", str(exc.reason))
    except (TimeoutError, OSError) as exc:
        return ("error", str(exc))


def check_http(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """Return ``(status, detail)`` for one HTTP(S) URL."""
    result = _fetch(url, timeout)
    if result is not None:
        return result
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return "ok", f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return "broken", f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return "error", str(exc.reason)
    except (TimeoutError, OSError) as exc:
        return "error", str(exc)


def check_local(link: Link, anchor_cache: dict[Path, set[str]]) -> tuple[str, str]:
    """Return ``(status, detail)`` for a relative-path or ``#anchor`` link."""
    if link.source is None:  # pragma: no cover - callers always set source
        return "error", "no source file to resolve against"
    parsed = urllib.parse.urlparse(link.url)
    fragment = urllib.parse.unquote(parsed.fragment)
    path_part = urllib.parse.unquote(parsed.path)

    if not path_part:  # "#anchor" in the same file
        target = link.source
    else:
        target = (link.source.parent / path_part).resolve()
        if not target.exists():
            return "broken", "file not found"
        if target.is_dir():  # a link to a directory is fine if it exists
            return "ok", "directory exists"
    if fragment:
        anchors = anchor_cache.setdefault(target, collect_anchors(target.read_text(errors="replace")))
        if fragment not in anchors:
            return "broken", f"anchor #{fragment} not found in {target.name}"
    return "ok", "file exists" if path_part else "anchor exists"


def check_links(
    links: Iterable[Link],
    *,
    timeout: float = 10.0,
    max_workers: int = 10,
    exclude: Iterable[str] = (),
) -> list[LinkResult]:
    """Check every link, returning results in the same order as *links*."""
    links = list(links)
    exclude_res = [re.compile(pattern) for pattern in exclude]
    http_cache: dict[str, tuple[str, str]] = {}
    anchor_cache: dict[Path, set[str]] = {}
    results: list[LinkResult | None] = [None] * len(links)
    http_jobs: list[tuple[int, Link]] = []

    for index, link in enumerate(links):
        if any(pattern.search(link.url) for pattern in exclude_res):
            results[index] = LinkResult(link, "skipped", "excluded by --exclude")
            continue
        scheme = urllib.parse.urlparse(link.url).scheme
        if scheme in ("http", "https"):
            http_jobs.append((index, link))
        elif scheme:  # mailto:, tel:, ftp:, data: … — not this tool's job
            results[index] = LinkResult(link, "skipped", f"{scheme}: scheme not checked")
        else:
            status, detail = check_local(link, anchor_cache)
            results[index] = LinkResult(link, status, detail)

    def _check_http_job(job: tuple[int, Link]) -> tuple[int, LinkResult]:
        index, link = job
        if link.url not in http_cache:
            http_cache[link.url] = check_http(link.url, timeout)
        status, detail = http_cache[link.url]
        return index, LinkResult(link, status, detail, checked_url=link.url)

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        for index, result in pool.map(_check_http_job, http_jobs):
            results[index] = result

    return [result for result in results if result is not None]
