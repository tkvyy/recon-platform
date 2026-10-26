import asyncio

import httpx

from app.engine import discovery


def test_parse_ct_records_filters_scope_and_wildcards():
    records = [
        {"name_value": "a.example.com\n*.example.com"},
        {"name_value": "B.Example.com"},
        {"name_value": "evil.com\nexample.com.evil.com"},
        {"name_value": "bad name.example.com"},
    ]
    found = discovery.parse_ct_records(records, "example.com")
    assert found == {"a.example.com", "b.example.com"}


def test_parse_ct_records_includes_apex():
    assert discovery.parse_ct_records([{"name_value": "example.com"}], "example.com") == {
        "example.com"
    }


def test_in_scope_rejects_lookalike_domains():
    assert discovery.in_scope("x.example.com", "example.com")
    assert not discovery.in_scope("badexample.com", "example.com")


def test_fetch_ct_parses_response():
    def handler(request):
        assert request.url.params["output"] == "json"
        return httpx.Response(200, json=[{"name_value": "api.example.com"}])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await discovery.fetch_ct("example.com", c)

    assert asyncio.run(run()) == {"api.example.com"}


def test_fetch_ct_html_error_page_returns_empty():
    def handler(request):
        return httpx.Response(200, text="<html>busy</html>")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await discovery.fetch_ct("example.com", c)

    assert asyncio.run(run()) == set()


def test_load_wordlist_dedups_validates_and_caps(tmp_path):
    f = tmp_path / "w.txt"
    f.write_text("www\nWWW\nbad word\n-bad\napi\ndev\n")
    assert discovery.load_wordlist(f, limit=10) == ["www", "api", "dev"]
    assert discovery.load_wordlist(f, limit=2) == ["www", "api"]


def test_default_wordlist_loads():
    assert len(discovery.load_wordlist()) > 50


def test_brute_candidates():
    assert discovery.brute_candidates("example.com", ["www", "api"]) == {
        "www.example.com",
        "api.example.com",
    }
