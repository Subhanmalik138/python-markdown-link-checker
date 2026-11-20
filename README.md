# Markdown Link Checker

Find broken links in Markdown documentation — before your readers do.

`linkcheck` scans Markdown files, extracts every link, and verifies it:

- **HTTP(S) links** are fetched concurrently (`HEAD` first, `GET` fallback for servers that refuse `HEAD`), following redirects.
- **Local links** (`other.md`, `../images/logo.png`) are resolved against the filesystem, relative to the file they appear in.
- **`#anchor` fragments** are checked against the target document's headings, using GitHub's slug rules (including the `-1`/`-2` suffixes for duplicate headings) and explicit `<a id="...">` anchors.
- **`mailto:` / `tel:` / `ftp:`** links are reported as skipped, not broken — this tool checks links, it doesn't validate email addresses.

Zero dependencies: standard library only. Exit code `1` when any link is broken or errored, so it drops straight into CI.

## Install

```bash
pip install .
# or run it without installing:
python -m linkcheck docs/
```

## Usage

```bash
# Check every Markdown file under docs/
linkcheck docs/

# Check one file, machine-readable output
linkcheck README.md --format json

# Skip internal URLs, faster timeout, more concurrency
linkcheck docs/ --exclude 'localhost|staging\.internal' --timeout 5 --max-workers 20
```

Example output:

```
docs/guide.md:
  line 42: https://example.com/old-page — broken: HTTP 404
  line 87: missing-file.md — broken: file not found
  line 103: #renamed-section — broken: anchor #renamed-section not found in guide.md
3 links checked: 41 ok, 3 broken, 0 errors, 0 skipped
```

## How it works

**Extraction** (`src/linkcheck/extractor.py`) recognises inline links and images, reference links (`[text][ref]`, `[text][]`, shortcut `[text]`), autolinks (`<https://…>`), and bare URLs. Fenced code blocks and inline code spans are masked out first — with newlines preserved, so reported line numbers are exact — because links inside examples are not links your readers can click.

**Checking** (`src/linkcheck/checker.py`) classifies each link by scheme, then verifies it. HTTP checks run in a thread pool; repeated URLs are fetched once and the result reused; anchor sets are cached per file. A URL that can't be reached at all (DNS failure, timeout, TLS error) is reported as an `error`, not `broken` — a network problem is not a judgement about the link.

**Anchors** (`src/linkcheck/anchors.py`) follow GitHub's rendering rules: headings are lower-cased, punctuation stripped, spaces become hyphens, and repeated headings get `-1`, `-2` suffixes. Setext headings (`===` / `---`) and explicit HTML anchors count too.

## Design decisions

1. **No external dependencies.** Link checking is I/O-bound string work; `urllib` plus `concurrent.futures` covers it, and zero dependencies means the tool installs anywhere and never breaks on a transitive upgrade.
2. **`error` is distinct from `broken`.** A 404 means the link is wrong; a DNS failure means the network is wrong. CI pipelines (and humans) should treat those differently, so the report keeps them separate.
3. **Code-aware extraction.** Documentation is full of links inside code examples that are meant to be copied, not clicked. Reporting them as broken would train users to ignore the tool, so code is masked before scanning.
4. **GitHub-faithful anchors.** Most Markdown is read on GitHub, so anchor validation reproduces GitHub's slug algorithm exactly — including duplicate-heading suffixes — instead of a looser approximation that would pass links GitHub itself would break.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `paths` | `.` | Files or directories to scan |
| `--format {text,json}` | `text` | Report format |
| `--exclude REGEX` | — | Skip links whose URL matches (repeatable) |
| `--timeout SECONDS` | `10` | Per-request HTTP timeout |
| `--max-workers N` | `10` | Concurrent HTTP requests |
| `--extensions LIST` | `.md,.markdown` | File extensions to scan |

## Running tests

```bash
python -m pytest
```

The suite (33 tests) covers extraction edge cases, slug generation, local/anchor verification, and the CLI end to end. HTTP behaviour is tested against a local server spun up in-process, so the tests need no network access.

## Tech stack

- Python 3.9+ (standard library only — `urllib`, `concurrent.futures`, `argparse`)
- pytest for tests
