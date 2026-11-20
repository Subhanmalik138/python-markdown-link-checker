"""Tests for link verification (HTTP + local files + anchors)."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from linkcheck.checker import check_http, check_links
from linkcheck.extractor import Link, extract_links


class _Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._respond(head=True)

    def do_GET(self):
        self._respond(head=False)

    def _respond(self, head):
        if self.path == "/ok":
            code = 200
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
            return
        elif self.path == "/head-not-allowed":
            code = 405 if head else 200
        else:
            code = 404
        self.send_response(code)
        self.send_header("Content-Length", "2")
        self.end_headers()
        if not head:
            self.wfile.write(b"ok")

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_http_ok(server):
    assert check_http(f"{server}/ok")[0] == "ok"


def test_http_404_is_broken(server):
    status, detail = check_http(f"{server}/missing")
    assert status == "broken"
    assert "404" in detail


def test_http_redirect_followed(server):
    assert check_http(f"{server}/redirect")[0] == "ok"


def test_http_head_not_allowed_falls_back_to_get(server):
    assert check_http(f"{server}/head-not-allowed")[0] == "ok"


def test_http_unreachable_is_error_not_broken():
    status, detail = check_http("http://127.0.0.1:1/nope", timeout=2)
    assert status == "error"
    assert detail


def test_local_file_links(tmp_path):
    doc = tmp_path / "index.md"
    doc.write_text("# Guide\n\n[ok](other.md) [gone](nope.md) [anchor](#guide)\n")
    (tmp_path / "other.md").write_text("# Other\n")
    results = {r.link.url: r.status for r in check_links(extract_links(doc.read_text(), source=doc))}
    assert results == {"other.md": "ok", "nope.md": "broken", "#guide": "ok"}


def test_local_anchor_missing_is_broken(tmp_path):
    doc = tmp_path / "index.md"
    doc.write_text("# Guide\n\n[bad](#no-such-section)\n")
    results = check_links(extract_links(doc.read_text(), source=doc))
    assert results[0].status == "broken"
    assert "no-such-section" in results[0].detail


def test_cross_file_anchor(tmp_path):
    doc = tmp_path / "index.md"
    (tmp_path / "other.md").write_text("## Real Heading\n")
    doc.write_text("[ok](other.md#real-heading) [bad](other.md#missing)\n")
    results = {r.link.url: r.status for r in check_links(extract_links(doc.read_text(), source=doc))}
    assert results == {"other.md#real-heading": "ok", "other.md#missing": "broken"}


def test_non_http_schemes_skipped(tmp_path):
    doc = tmp_path / "index.md"
    doc.write_text("[mail](mailto:a@b.com) [call](tel:+123) [ftp](ftp://example.com/x)\n")
    results = check_links(extract_links(doc.read_text(), source=doc))
    assert all(r.status == "skipped" for r in results)


def test_exclude_pattern_skips_matching_links(tmp_path):
    doc = tmp_path / "index.md"
    doc.write_text("[a](https://internal.example.com/x) [b](https://nonexistent.invalid/y)\n")
    results = check_links(
        extract_links(doc.read_text(), source=doc),
        exclude=[r"internal\.example\.com"],
    )
    by_url = {r.link.url: r.status for r in results}
    assert by_url["https://internal.example.com/x"] == "skipped"
    # .invalid never resolves, so the un-excluded link errors (not "broken").
    assert by_url["https://nonexistent.invalid/y"] == "error"


def test_duplicate_urls_fetched_once(tmp_path, server):
    doc = tmp_path / "index.md"
    doc.write_text(f"[a]({server}/ok) [b]({server}/ok)\n")
    results = check_links(extract_links(doc.read_text(), source=doc))
    assert [r.status for r in results] == ["ok", "ok"]


def test_results_keep_input_order(tmp_path, server):
    doc = tmp_path / "index.md"
    doc.write_text(f"[a]({server}/missing) [b]({server}/ok) [c]({server}/missing)\n")
    results = check_links(extract_links(doc.read_text(), source=doc))
    assert [r.link.url for r in results] == [
        f"{server}/missing", f"{server}/ok", f"{server}/missing",
    ]
    assert [r.status for r in results] == ["broken", "ok", "broken"]
