"""Optional adapters for external recon tools (Subfinder, HTTPx).

Kept only for benchmarking the built-in engine in app/engine. Not used by the app.
"""
import json
import subprocess



class ReconError(Exception):
    """Raised when an external recon tool fails, times out, or is missing."""


def _run(cmd: list[str], input_text: str | None = None, timeout: int = 300) -> str:
    """Run a CLI tool safely (no shell) and return its stdout."""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ReconError(f"{cmd[0]} is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        raise ReconError(f"{cmd[0]} timed out after {timeout}s")
    if result.returncode != 0:
        raise ReconError(f"{cmd[0]} failed: {result.stderr.strip()}")
    return result.stdout


def run_subfinder(domain: str) -> list[str]:
    """Passive subdomain discovery. Returns a deduplicated, sorted list."""
    output = _run(["subfinder", "-d", domain, "-silent"], timeout=300)
    hosts = {line.strip().lower() for line in output.splitlines() if line.strip()}
    return sorted(hosts)


def run_httpx(hosts: list[str]) -> list[dict]:
    """Probe hosts for live web services. Returns one dict per live host."""
    if not hosts:
        return []
    output = _run(
        ["httpx", "-silent", "-json", "-ip", "-tech-detect", "-status-code",
         "-timeout", "10", "-rl", "20"],
        input_text="\n".join(hosts),
        timeout=600,
    )
    assets = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip any non-JSON noise
        assets.append({
            "hostname": data.get("input"),
            "ip_address": data.get("host_ip") or data.get("host"),
            "http_status": data.get("status_code"),
            "tech_stack": data.get("tech", []),
        })
    return assets


def run_external_recon(domain: str) -> dict:
    """OPTIONAL: Subfinder + HTTPx pipeline, used only to benchmark the built-in engine.

    The application never depends on this; it works without either tool installed.
    """
    hosts = run_subfinder(domain)
    assets = run_httpx(hosts)
    return {"domain": domain, "raw_count": len(hosts), "assets": assets}
