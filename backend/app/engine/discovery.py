"""Own subdomain discovery: certificate transparency + wordlist generation (FR3, FR4)."""
import re
from pathlib import Path

import httpx

CRT_URL = "https://crt.sh/"
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


async def fetch_ct(domain: str, client: httpx.AsyncClient, timeout: float = 30.0) -> set[str]:
    """Query crt.sh for certificates issued to *.domain. Returns hostnames."""
    resp = await client.get(
        CRT_URL, params={"q": f"%.{domain}", "output": "json"}, timeout=timeout
    )
    resp.raise_for_status()
    try:
        records = resp.json()
    except ValueError:
        return set()  # crt.sh sometimes returns an HTML error page
    return parse_ct_records(records, domain)


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
