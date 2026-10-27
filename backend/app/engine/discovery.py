"""Own subdomain discovery: certificate transparency + wordlist generation (FR3, FR4)."""
import asyncio
import re
from pathlib import Path

import httpx

CRT_URL = "https://crt.sh/"
CERTSPOTTER_URL = "https://api.certspotter.com/v1/issuances"
HOST_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
DEFAULT_WORDLIST = Path(__file__).with_name("wordlist.txt")


def in_scope(name: str, domain: str) -> bool:
    """True if name is the domain itself or a subdomain of it."""
    return name == domain or name.endswith("." + domain)


def clean_name(raw: str) -> str | None:
    """Normalise a certificate name; drop wildcards and anything malformed."""
    name = raw.strip().lower().rstrip(".")
    if not name or name.startswith("*."):
        return None
    labels = name.split(".")
    if len(labels) < 2 or not all(HOST_LABEL.match(label) for label in labels):
        return None
    return name


def parse_ct_records(records: list[dict], domain: str) -> set[str]:
    """Pure function: turn crt.sh JSON rows into a set of in-scope hostnames."""
    found: set[str] = set()
    for row in records:
        for raw in str(row.get("name_value", "")).splitlines():
            name = clean_name(raw)
            if name and in_scope(name, domain):
                found.add(name)
    return found


class CTUnavailable(Exception):
    """Every certificate transparency source failed."""


def describe_error(exc: Exception) -> str:
    """A short, readable reason (httpx errors often have an empty message)."""
    if isinstance(exc, CTUnavailable):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def parse_certspotter(records: list[dict], domain: str) -> set[str]:
    """Pure function: turn Cert Spotter issuance rows into in-scope hostnames."""
    found: set[str] = set()
    for row in records:
        for raw in row.get("dns_names", []):
            name = clean_name(str(raw))
            if name and in_scope(name, domain):
                found.add(name)
    return found


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    timeout: float,
    attempts: int,
    backoff: float,
):
    """GET a JSON document, retrying transient failures with a growing pause."""
    last: Exception = RuntimeError("no attempts made")
    for attempt in range(1, attempts + 1):
        try:
            resp = await client.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()  # ValueError if the server sent an HTML error page
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            if attempt < attempts:
                await asyncio.sleep(backoff * attempt)
    raise last


async def fetch_crtsh(domain, client, timeout=30.0, attempts=3, backoff=1.5) -> set[str]:
    records = await _get_json(
        client, CRT_URL, {"q": f"%.{domain}", "output": "json"}, timeout, attempts, backoff
    )
    return parse_ct_records(records, domain)


async def fetch_certspotter(domain, client, timeout=30.0, attempts=2, backoff=1.5) -> set[str]:
    records = await _get_json(
        client,
        CERTSPOTTER_URL,
        {"domain": domain, "include_subdomains": "true", "expand": "dns_names"},
        timeout,
        attempts,
        backoff,
    )
    return parse_certspotter(records, domain)


async def fetch_ct(
    domain: str,
    client: httpx.AsyncClient,
    timeout: float = 30.0,
    backoff: float = 1.5,
) -> set[str]:
    """Certificate transparency lookup: crt.sh first, Cert Spotter as a fallback.

    Each source is retried. Raises CTUnavailable only if both fail.
    """
    reasons = []
    for label, fetch in (("crt.sh", fetch_crtsh), ("Cert Spotter", fetch_certspotter)):
        try:
            return await fetch(domain, client, timeout=timeout, backoff=backoff)
        except (httpx.HTTPError, ValueError) as exc:
            reasons.append(f"{label}: {describe_error(exc)}")
    raise CTUnavailable("; ".join(reasons))


def load_wordlist(path: Path | None = None, limit: int = 5000) -> list[str]:
    """Read a wordlist, keeping only valid, unique DNS labels (capped at limit)."""
    words: list[str] = []
    seen: set[str] = set()
    for line in (path or DEFAULT_WORDLIST).read_text().splitlines():
        word = line.strip().lower()
        if word and word not in seen and HOST_LABEL.match(word):
            seen.add(word)
            words.append(word)
            if len(words) >= limit:
                break
    return words


def brute_candidates(domain: str, words: list[str]) -> set[str]:
    return {f"{word}.{domain}" for word in words}
