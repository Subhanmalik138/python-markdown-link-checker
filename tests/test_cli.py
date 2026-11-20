"""End-to-end CLI tests on temporary file trees."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from linkcheck.cli import main


class _Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200 if self.path == "/ok" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.do_HEAD()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_cli_reports_broken_link_and_exits_1(tmp_path, capsys, server):
    doc = tmp_path / "README.md"
    doc.write_text(f"[good]({server}/ok)\n[bad]({server}/missing)\n[local](gone.md)\n")
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "3 links checked: 1 ok, 2 broken, 0 errors, 0 skipped" in out
    assert "line 2:" in out and "line 3:" in out


def test_cli_clean_tree_exits_0(tmp_path, capsys, server):
    doc = tmp_path / "README.md"
    doc.write_text(f"# Title\n\n[good]({server}/ok) [anchor](#title)\n")
    assert main([str(doc)]) == 0
    assert "2 links checked: 2 ok" in capsys.readouterr().out


def test_cli_json_format(tmp_path, capsys, server):
    doc = tmp_path / "README.md"
    doc.write_text(f"[bad]({server}/missing)\n")
    assert main([str(doc), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"] == {"broken": 1}
    assert payload["results"][0]["status"] == "broken"
    assert payload["results"][0]["line"] == 1


def test_cli_missing_path_exits_2(tmp_path, capsys):
    assert main([str(tmp_path / "nope.md")]) == 2
    assert "no Markdown files found" in capsys.readouterr().err


def test_cli_scans_directory_recursively(tmp_path, capsys, server):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.md").write_text(f"[x]({server}/ok)\n")
    (tmp_path / "sub" / "b.markdown").write_text(f"[y]({server}/missing)\n")
    (tmp_path / "notes.txt").write_text(f"[z]({server}/missing)\n")  # not scanned
    assert main([str(tmp_path)]) == 1
    assert "2 links checked: 1 ok, 1 broken" in capsys.readouterr().out
