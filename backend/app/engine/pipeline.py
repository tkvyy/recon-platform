"""The built-in recon pipeline: discover -> resolve -> filter -> probe."""
import logging
from typing import Awaitable, Callable

import httpx

from app.engine import discovery, probe, resolver
from app.engine.config import ScanConfig

log = logging.getLogger(__name__)
USER_AGENT = "ReconPlatform/0.1 (authorized security assessment)"

CTFetch = Callable[[str, httpx.AsyncClient], Awaitable[set[str]]]


async def scan_domain(
    domain: str,
    config: ScanConfig | None = None,
    lookup: resolver.Lookup | None = None,
    client: httpx.AsyncClient | None = None,
    wordlist: list[str] | None = None,
    ct_fetch: CTFetch | None = None,
) -> dict:
    """Run a full scan of `domain` with the built-in engine.

    Dependencies (lookup, client, wordlist, ct_fetch) are injectable so the
    pipeline can be unit tested without a network (NFR5, NFR6).
    Returns {"domain", "raw_count", "assets", "warnings"}.
    """
    config = config or ScanConfig()
    lookup = lookup or resolver.make_lookup(timeout=config.dns_timeout)
    own_client = client is None
    client = client or httpx.AsyncClient(
        verify=False, headers={"User-Agent": USER_AGENT}
    )
    ct_fetch = ct_fetch or discovery.fetch_ct
    warnings: list[str] = []

    try:
        # 1. Discovery -------------------------------------------------------
        ct_hosts: set[str] = set()
        if config.use_ct:
            try:
                ct_hosts = await ct_fetch(domain, client)
            except Exception as exc:  # CT is a source, not a requirement (NFR4)
                warnings.append(f"Certificate transparency lookup failed: {exc}")

        brute_hosts: set[str] = set()
        if config.use_bruteforce:
            words = wordlist if wordlist is not None else discovery.load_wordlist(
                limit=config.max_wordlist
            )
            brute_hosts = discovery.brute_candidates(domain, words[: config.max_wordlist])

        candidates = ct_hosts | brute_hosts | {domain}

        # 2. Resolve (FR4, FR6) ---------------------------------------------
        resolved = await resolver.resolve_many(
            candidates, lookup, config.dns_concurrency
        )

        # 3. Wildcard filtering (FR5): brute-forced names that only resolve to
        #    wildcard IPs are false positives. CT names are real certificates,
        #    so they are always kept.
        wildcard_ips: set[str] = set()
        if config.use_bruteforce:
            wildcard_ips = await resolver.detect_wildcard(
                domain, lookup, config.wildcard_probes
            )
            if wildcard_ips:
                warnings.append(
                    "Wildcard DNS detected; brute-force results were filtered"
                )
        hosts = {
            name: info
            for name, info in resolved.items()
            if name in ct_hosts
            or name == domain
            or not resolver.is_wildcard_hit(info, wildcard_ips)
        }

        # 4. Probe (FR7) ------------------------------------------------------
        probed = await probe.probe_many(
            sorted(hosts), client, config.http_concurrency, config.http_timeout
        )
    finally:
        if own_client:
            await client.aclose()

    assets = []
    for name in sorted(hosts):
        info = hosts[name]
        web = probed.get(name) or {}
        sources = []
        if name in ct_hosts:
            sources.append("ct")
        if name in brute_hosts:
            sources.append("bruteforce")
        assets.append(
            {
                "hostname": name,
                "ip_address": info["ips"][0] if info["ips"] else None,
                "ips": info["ips"],
                "cname": info["cnames"],
                "scheme": web.get("scheme"),
                "http_status": web.get("http_status"),
                "title": web.get("title"),
                "headers": web.get("headers", {}),
                "redirect_url": web.get("redirect_url"),
                "tech_stack": web.get("tech_stack", []),
                "sources": sources or ["apex"],
            }
        )
    return {
        "domain": domain,
        "raw_count": len(candidates),
        "assets": assets,
        "warnings": warnings,
    }
