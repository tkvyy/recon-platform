"""Entry point used by the Celery worker. Runs the built-in engine (app/engine)."""
import asyncio
import json

from app.engine.config import ScanConfig
from app.engine.pipeline import scan_domain
from app.validators import is_valid_domain, normalize_domain


def run_recon(domain: str, config: ScanConfig | None = None) -> dict:
    """Validate the domain, then run the built-in discovery + probing pipeline."""
    domain = normalize_domain(domain)
    if not is_valid_domain(domain):
        raise ValueError(f"Invalid domain: {domain!r}")
    return asyncio.run(scan_domain(domain, config))


if __name__ == "__main__":
    import sys

    print(json.dumps(run_recon(sys.argv[1]), indent=2))
