import asyncio

import httpx

from app.engine.config import ScanConfig
from app.engine.pipeline import scan_domain


def web_client():
    def handler(request):
        return httpx.Response(200, text="<title>Site</title>", headers={"Server": "nginx"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(table, ct=None, wordlist=("www", "api"), config=None, wildcard=None):
    async def lookup(name):
        if name in table:
            return table[name]
        return wildcard  # None = NXDOMAIN, dict = wildcard answer

    async def ct_fetch(domain, client):
        if isinstance(ct, Exception):
            raise ct
        return set(ct or [])

    async def go():
        async with web_client() as c:
            return await scan_domain(
                "example.com",
                config or ScanConfig(),
                lookup=lookup,
                client=c,
                wordlist=list(wordlist),
                ct_fetch=ct_fetch,
            )

    return asyncio.run(go())


A = {"ips": ["1.1.1.1"], "cnames": []}


def test_combines_ct_and_bruteforce_sources():
    table = {"example.com": A, "www.example.com": A, "old.example.com": A}
    res = run(table, ct=["old.example.com"])
    by_host = {a["hostname"]: a for a in res["assets"]}
    assert set(by_host) == {"example.com", "www.example.com", "old.example.com"}
    assert by_host["old.example.com"]["sources"] == ["ct"]
    assert by_host["www.example.com"]["sources"] == ["bruteforce"]
    assert by_host["www.example.com"]["http_status"] == 200
    assert by_host["www.example.com"]["title"] == "Site"


def test_wildcard_dns_filters_bruteforce_false_positives():
    wild = {"ips": ["9.9.9.9"], "cnames": []}
    table = {"example.com": A, "real.example.com": A}
    # every other name resolves to the wildcard IP
    res = run(table, ct=["real.example.com"], wildcard=wild, wordlist=["www", "api", "mail"])
    hosts = {a["hostname"] for a in res["assets"]}
    assert hosts == {"example.com", "real.example.com"}
    assert any("Wildcard" in w for w in res["warnings"])


def test_ct_names_survive_wildcard_filter():
    wild = {"ips": ["9.9.9.9"], "cnames": []}
    table = {"example.com": A, "cert.example.com": wild}
    res = run(table, ct=["cert.example.com"], wildcard=wild, wordlist=[])
    assert "cert.example.com" in {a["hostname"] for a in res["assets"]}


def test_ct_failure_is_a_warning_not_a_crash():
    res = run({"example.com": A, "www.example.com": A}, ct=RuntimeError("crt.sh down"))
    assert {a["hostname"] for a in res["assets"]} == {"example.com", "www.example.com"}
    assert any("Certificate transparency" in w and "RuntimeError" in w for w in res["warnings"])


def test_bruteforce_can_be_disabled():
    table = {"example.com": A, "www.example.com": A}
    res = run(table, ct=[], config=ScanConfig(use_bruteforce=False))
    assert {a["hostname"] for a in res["assets"]} == {"example.com"}


def test_records_cnames():
    table = {"example.com": A, "app.example.com": {"ips": ["2.2.2.2"], "cnames": ["x.herokuapp.com"]}}
    res = run(table, ct=["app.example.com"], wordlist=[])
    app = next(a for a in res["assets"] if a["hostname"] == "app.example.com")
    assert app["cname"] == ["x.herokuapp.com"]
