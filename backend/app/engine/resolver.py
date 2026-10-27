"""Own async DNS resolver with wildcard detection (FR4, FR5, FR6)."""
import asyncio
import secrets
from typing import Awaitable, Callable

import dns.asyncresolver
import dns.exception
import dns.rdatatype
import dns.resolver

# A lookup takes a hostname and returns {"ips": [...], "cnames": [...]} or None.
Lookup = Callable[[str], Awaitable[dict | None]]


def make_lookup(timeout: float = 3.0, nameservers: list[str] | None = None) -> Lookup:
    """Build the real DNS lookup function (dnspython, A records + CNAME chain)."""
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout
    if nameservers:
        resolver.nameservers = nameservers

    async def lookup(name: str) -> dict | None:
        try:
            answer = await resolver.resolve(name, "A")
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            return None
        ips = sorted({r.address for r in answer})
        cnames = [
            str(rr.target).rstrip(".").lower()
            for rrset in answer.response.answer
            if rrset.rdtype == dns.rdatatype.CNAME
            for rr in rrset
        ]
        return {"ips": ips, "cnames": cnames}

    return lookup


async def detect_wildcard(domain: str, lookup: Lookup, probes: int = 3) -> set[str]:
    """Resolve random, surely-nonexistent labels. Any IPs returned are wildcard IPs."""
    names = [f"{secrets.token_hex(8)}.{domain}" for _ in range(probes)]
    results = await asyncio.gather(*(lookup(n) for n in names))
    wildcard_ips: set[str] = set()
    for res in results:
        if res:
            wildcard_ips.update(res["ips"])
    return wildcard_ips


async def resolve_many(
    names: set[str] | list[str],
    lookup: Lookup,
    concurrency: int = 50,
    cancel: asyncio.Event | None = None,
) -> dict[str, dict]:
    """Resolve many names concurrently; return only those that resolve.

    If `cancel` is set, names not yet started are skipped.
    """
    sem = asyncio.Semaphore(concurrency)

    async def one(name: str):
        async with sem:
            if cancel is not None and cancel.is_set():
                return name, None
            try:
                return name, await lookup(name)
            except Exception:  # a single bad lookup must not sink the scan (NFR4)
                return name, None

    pairs = await asyncio.gather(*(one(n) for n in names))
    return {name: info for name, info in pairs if info}


def is_wildcard_hit(info: dict, wildcard_ips: set[str]) -> bool:
    """A brute-forced host is a false positive if it only resolves to wildcard IPs."""
    return bool(wildcard_ips) and set(info["ips"]) <= wildcard_ips
