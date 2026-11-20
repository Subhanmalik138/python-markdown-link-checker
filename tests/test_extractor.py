"""Tests for Markdown link extraction."""

from linkcheck.extractor import extract_links


def urls(text):
    return [(link.url, link.line, link.kind) for link in extract_links(text)]


def test_inline_link_and_image():
    links = urls("See [the docs](https://example.com/guide) and ![logo](img/logo.png).\n")
    assert ("https://example.com/guide", 1, "link") in links
    assert ("img/logo.png", 1, "image") in links


def test_inline_link_with_title_and_angle_destination():
    links = urls('[a](<https://example.com/x y> "Title")\n[b](https://example.com "T")\n')
    assert ("https://example.com/x y", 1, "link") in links
    assert ("https://example.com", 2, "link") in links


def test_reference_links():
    text = (
        "[guide][g] and [short] and [empty][]\n\n"
        "[g]: https://example.com/guide\n"
        "[short]: https://example.com/short\n"
        "[empty]: https://example.com/empty\n"
    )
    found = {url for url, _, _ in urls(text)}
    assert found == {
        "https://example.com/guide",
        "https://example.com/short",
        "https://example.com/empty",
    }


def test_undefined_reference_is_not_a_link():
    assert urls("[missing][nope]\n") == []


def test_autolinks_and_bare_urls():
    links = urls("Visit <https://example.com/auto> or https://example.com/bare.\n")
    found = {url for url, _, _ in links}
    assert found == {"https://example.com/auto", "https://example.com/bare"}


def test_bare_url_trailing_punctuation_stripped():
    links = urls("See https://example.com/page, and (https://example.com/other).\n")
    found = {url for url, _, _ in links}
    assert found == {"https://example.com/page", "https://example.com/other"}


def test_code_blocks_and_spans_are_ignored():
    text = (
        "```\n[hidden](https://example.com/hidden)\n```\n"
        "Use `[code](https://example.com/code)` inline.\n"
        "[visible](https://example.com/visible)\n"
    )
    assert urls(text) == [("https://example.com/visible", 5, "link")]


def test_line_numbers_are_exact():
    text = "intro\n\n[one](https://example.com/1)\n\n[two](https://example.com/2)\n"
    assert urls(text) == [
        ("https://example.com/1", 3, "link"),
        ("https://example.com/2", 5, "link"),
    ]


def test_fragment_and_relative_links_extracted():
    links = urls("[a](#section) [b](other.md#part) [c](../up.md)\n")
    found = {url for url, _, _ in links}
    assert found == {"#section", "other.md#part", "../up.md"}


def test_mailto_extracted_for_classifier():
    links = urls("[mail](mailto:hi@example.com)\n")
    assert links == [("mailto:hi@example.com", 1, "link")]
