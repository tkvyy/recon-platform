import asyncio

from app.engine import resolver


def make_fake(table):
    async def lookup(name):
        return table.get(name)

    return lookup


def test_resolve_many_returns_only_resolving_names():
    lookup = make_fake({"a.example.com": {"ips": ["1.1.1.1"], "cnames": []}})
    out = asyncio.run(resolver.resolve_many({"a.example.com", "b.example.com"}, lookup))
    assert list(out) == ["a.example.com"]


def test_resolve_many_survives_lookup_errors():
    async def lookup(name):
        if name == "boom.example.com":
            raise RuntimeError("dns exploded")
        return {"ips": ["1.1.1.1"], "cnames": []}

    out = asyncio.run(resolver.resolve_many({"boom.example.com", "ok.example.com"}, lookup))
    assert list(out) == ["ok.example.com"]


def test_resolve_many_respects_concurrency_limit():
    active = peak = 0

    async def lookup(name):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"ips": ["1.1.1.1"], "cnames": []}

    names = {f"h{i}.example.com" for i in range(30)}
    asyncio.run(resolver.resolve_many(names, lookup, concurrency=5))
    assert peak <= 5


def test_detect_wildcard_finds_ips():
    async def lookup(name):
        return {"ips": ["9.9.9.9"], "cnames": []}

    assert asyncio.run(resolver.detect_wildcard("example.com", lookup)) == {"9.9.9.9"}


def test_detect_wildcard_none_when_nxdomain():
    async def lookup(name):
        return None

    assert asyncio.run(resolver.detect_wildcard("example.com", lookup)) == set()


def test_is_wildcard_hit():
    assert resolver.is_wildcard_hit({"ips": ["9.9.9.9"]}, {"9.9.9.9"})
    assert not resolver.is_wildcard_hit({"ips": ["1.1.1.1"]}, {"9.9.9.9"})
    assert not resolver.is_wildcard_hit({"ips": ["9.9.9.9"]}, set())
