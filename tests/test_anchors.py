"""Tests for GitHub-style anchor slug generation and collection."""

from linkcheck.anchors import collect_anchors, slugify


def test_slugify_basics():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  Getting  Started  ") == "getting-started"
    assert slugify("C++ Guide") == "c-guide"
    assert slugify("don't_stop") == "dont_stop"
    assert slugify("API v2.0 Notes") == "api-v20-notes"


def test_atx_headings_collected():
    doc = "# Title\n\n## Sub Section\n\n### Deep Dive\n"
    assert collect_anchors(doc) == {"title", "sub-section", "deep-dive"}


def test_duplicate_headings_get_github_suffixes():
    doc = "# Setup\n\n## Setup\n\n## Setup\n"
    assert collect_anchors(doc) == {"setup", "setup-1", "setup-2"}


def test_setext_headings_collected():
    doc = "Title\n=====\n\nSub\n---\n"
    assert collect_anchors(doc) == {"title", "sub"}


def test_html_anchors_collected():
    doc = '<a id="custom-anchor"></a>\n<a name="old-style"></a>\n'
    assert collect_anchors(doc) == {"custom-anchor", "old-style"}


def test_headings_in_code_blocks_ignored():
    doc = "```\n# Not A Heading\n```\n\n# Real Heading\n"
    assert collect_anchors(doc) == {"real-heading"}
