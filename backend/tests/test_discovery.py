import asyncio

import httpx
import pytest

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


def run_ct(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await discovery.fetch_ct("example.com", c, backoff=0)

    return asyncio.run(go())


def test_fetch_ct_parses_crtsh_response():
    def handler(request):
        assert request.url.host == "crt.sh"
        assert request.url.params["output"] == "json"
        return httpx.Response(200, json=[{"name_value": "api.example.com"}])

    assert run_ct(handler) == {"api.example.com"}


def test_fetch_ct_retries_a_transient_failure():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        if len(calls) == 1:
            return httpx.Response(404)
        return httpx.Response(200, json=[{"name_value": "api.example.com"}])

    assert run_ct(handler) == {"api.example.com"}
    assert calls == ["crt.sh", "crt.sh"]  # retried crt.sh, no fallback needed


def test_fetch_ct_falls_back_to_certspotter():
    def handler(request):
        if request.url.host == "crt.sh":
            return httpx.Response(404)
        assert request.url.params["include_subdomains"] == "true"
        return httpx.Response(
            200, json=[{"dns_names": ["shop.example.com", "*.example.com", "evil.com"]}]
        )

    assert run_ct(handler) == {"shop.example.com"}


def test_fetch_ct_html_error_page_counts_as_failure_and_falls_back():
    def handler(request):
        if request.url.host == "crt.sh":
            return httpx.Response(200, text="<html>busy</html>")
        return httpx.Response(200, json=[{"dns_names": ["a.example.com"]}])

    assert run_ct(handler) == {"a.example.com"}


def test_fetch_ct_raises_with_both_reasons_when_everything_fails():
    def handler(request):
        if request.url.host == "crt.sh":
            return httpx.Response(404)
        raise httpx.ReadTimeout("")  # empty message, like the real thing

    with pytest.raises(discovery.CTUnavailable) as exc:
        run_ct(handler)
    msg = str(exc.value)
    assert "crt.sh: HTTP 404" in msg
    assert "Cert Spotter: ReadTimeout" in msg


def test_parse_certspotter_scopes_and_cleans():
    rows = [{"dns_names": ["A.example.com", "*.example.com", "x.other.com", "bad name.example.com"]}]
    assert discovery.parse_certspotter(rows, "example.com") == {"a.example.com"}


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
