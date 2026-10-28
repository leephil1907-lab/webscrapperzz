import json
import httpx
import pytest

from recovery import parse_target
from app import extract


def test_parse_target_adds_https():
    assert parse_target("example.com") == "https://example.com/"


def test_parse_target_rejects_unsupported_schemes():
    with pytest.raises(ValueError):
        parse_target("file:///etc/passwd")


def test_parse_target_rejects_credentials():
    with pytest.raises(ValueError):
        parse_target("https://user:secret@example.com")


def test_extract_preserves_json_ld_and_visible_text():
    html = """<!doctype html><html lang="en"><head><title>Sample page</title>
    <meta name="description" content="A sample description">
    <script type="application/ld+json">{"@type":"Organization","name":"Sample Co"}</script>
    </head><body><h1>Hello world</h1><p>Contact info@example.com</p></body></html>"""
    response = httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        text=html,
        request=httpx.Request("GET", "https://example.com/"),
    )
    result = extract("https://example.com/", response)
    assert result["title"] == "Sample page"
    assert "Hello world" in result["text"]
    assert "info@example.com" in result["emails"]
    assert result["assets"][0]["type"] == "json-ld"
    assert result["assets"][0]["data"]["name"] == "Sample Co"
