"""Own async HTTP prober (FR7)."""
import asyncio
import re

import httpx

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
KEEP_HEADERS = (
    "server",
    "x-powered-by",
    "content-type",
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
)
MAX_BODY = 65536


def extract_title(html: str) -> str | None:
    match = TITLE_RE.search(html[:MAX_BODY])
    if not match:
        return None
    title = " ".join(match.group(1).split())
    return title[:200] or None


def guess_tech(headers: dict) -> list[str]:
    """Very small header-based fingerprint (Server / X-Powered-By)."""
    tech = []
    for key in ("server", "x-powered-by"):
        value = headers.get(key)
        if value:
            tech.append(value.split("/")[0].strip())
    return tech


async def probe_host(client: httpx.AsyncClient, host: str, timeout: float = 8.0) -> dict | None:
    """Try HTTPS then HTTP. Return a summary dict, or None if neither answers."""
    for scheme in ("https", "http"):
        try:
            resp = await client.get(
                f"{scheme}://{host}/", timeout=timeout, follow_redirects=False
            )
        except httpx.HTTPError:
            continue
        headers = {k: v for k, v in resp.headers.items() if k.lower() in KEEP_HEADERS}
        headers = {k.lower(): v for k, v in headers.items()}
        return {
            "scheme": scheme,
            "http_status": resp.status_code,
            "title": extract_title(resp.text),
            "headers": headers,
            "redirect_url": resp.headers.get("location"),
            "tech_stack": guess_tech(headers),
        }
    return None


async def probe_many(
    hosts: list[str],
    client: httpx.AsyncClient,
    concurrency: int = 20,
    timeout: float = 8.0,
    cancel: asyncio.Event | None = None,
) -> dict[str, dict]:
    """Probe hosts concurrently; return only those that answered over HTTP(S).

    If `cancel` is set, hosts not yet started are skipped.
    """
    sem = asyncio.Semaphore(concurrency)

    async def one(host: str):
        async with sem:
            if cancel is not None and cancel.is_set():
                return host, None
            try:
                return host, await probe_host(client, host, timeout)
            except Exception:  # NFR4: one failure must not abort the scan
                return host, None

    pairs = await asyncio.gather(*(one(h) for h in hosts))
    return {h: info for h, info in pairs if info}
