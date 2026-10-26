import asyncio

import httpx

from app.engine import probe


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_extract_title():
    assert probe.extract_title("<html><TITLE>\n Hello  World </title>") == "Hello World"
    assert probe.extract_title("<html>no title</html>") is None


def test_probe_host_records_fields():
    def handler(request):
        return httpx.Response(
            301,
            headers={"Server": "nginx/1.25", "Location": "https://x.example.com/login"},
            text="<title>Moved</title>",
        )

    async def run():
        async with client_for(handler) as c:
            return await probe.probe_host(c, "x.example.com")

    r = asyncio.run(run())
    assert r["scheme"] == "https"
    assert r["http_status"] == 301
    assert r["title"] == "Moved"
    assert r["redirect_url"] == "https://x.example.com/login"
    assert r["headers"]["server"] == "nginx/1.25"
    assert r["tech_stack"] == ["nginx"]


def test_probe_falls_back_to_http():
    def handler(request):
        if request.url.scheme == "https":
            raise httpx.ConnectError("tls down")
        return httpx.Response(200, text="ok")

    async def run():
        async with client_for(handler) as c:
            return await probe.probe_host(c, "x.example.com")

    assert asyncio.run(run())["scheme"] == "http"


def test_probe_returns_none_when_unreachable():
    def handler(request):
        raise httpx.ConnectError("down")

    async def run():
        async with client_for(handler) as c:
            return await probe.probe_host(c, "x.example.com")

    assert asyncio.run(run()) is None


def test_probe_many_skips_failures():
    def handler(request):
        if request.url.host == "down.example.com":
            raise httpx.ConnectError("down")
        return httpx.Response(200, text="<title>Up</title>")

    async def run():
        async with client_for(handler) as c:
            return await probe.probe_many(["up.example.com", "down.example.com"], c)

    out = asyncio.run(run())
    assert list(out) == ["up.example.com"]
