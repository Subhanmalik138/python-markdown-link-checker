"""linkcheck — find broken links in Markdown documentation.

A zero-dependency CLI that scans Markdown files for links, then verifies
each one: HTTP(S) links are fetched concurrently, local file links are
resolved against the filesystem, and ``#anchor`` fragments are checked
against the headings of the target document.
"""

from .checker import LinkResult, check_links
from .extractor import Link, extract_links

__all__ = ["Link", "LinkResult", "check_links", "extract_links"]
__version__ = "1.0.0"
