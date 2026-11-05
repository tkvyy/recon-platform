"""Benchmark the built-in engine on ONE domain you own or are authorised to test.

Usage (from the backend folder, venv active):
    python scripts/benchmark.py example.com
    python scripts/benchmark.py example.com --runs 3
    python scripts/benchmark.py example.com --runs 3 --compare   # also run Subfinder + HTTPx

Prints per-run timings for each stage and a summary you can paste into the report.
"""
import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import discovery, probe, resolver  # noqa: E402
from app.engine.config import ScanConfig  # noqa: E402
from app.engine.pipeline import scan_domain  # noqa: E402
from app.validators import is_valid_domain, normalize_domain  # noqa: E402

timings: dict[str, float] = {}


def instrument(module, name: str, label: str) -> None:
    """Wrap an async engine function so its elapsed time is recorded."""
    original = getattr(module, name)

    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await original(*args, **kwargs)
        finally:
            timings[label] = timings.get(label, 0.0) + time.perf_counter() - start

    setattr(module, name, wrapper)


def run_once(domain: str, config: ScanConfig) -> dict:
    timings.clear()
    start = time.perf_counter()
    result = asyncio.run(scan_domain(domain, config))
    total = time.perf_counter() - start
    assets = result["assets"]
    return {
        "total": total,
        "ct": timings.get("ct", 0.0),
        "dns": timings.get("dns", 0.0),
        "probe": timings.get("probe", 0.0),
        "hosts": len(assets),
        "web": sum(1 for a in assets if a["http_status"] is not None),
        "warnings": result["warnings"],
        "names": {a["hostname"] for a in assets},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--compare", action="store_true", help="also time Subfinder + HTTPx")
    args = parser.parse_args()

    domain = normalize_domain(args.domain)
    if not is_valid_domain(domain):
        sys.exit(f"Invalid domain: {domain!r}")

    instrument(discovery, "fetch_ct", "ct")
    instrument(resolver, "resolve_many", "dns")
    instrument(probe, "probe_many", "probe")

    config = ScanConfig()
    print(f"Benchmarking {domain}: {args.runs} run(s), "
          f"dns_concurrency={config.dns_concurrency}, http_concurrency={config.http_concurrency}\n")
    print(f"{'run':>3} {'total s':>8} {'CT s':>7} {'DNS s':>7} {'probe s':>8} {'hosts':>6} {'web':>5}")

    runs = []
    for i in range(1, args.runs + 1):
        r = run_once(domain, config)
        runs.append(r)
        print(f"{i:>3} {r['total']:>8.2f} {r['ct']:>7.2f} {r['dns']:>7.2f} "
              f"{r['probe']:>8.2f} {r['hosts']:>6} {r['web']:>5}")
        for w in r["warnings"]:
            print(f"      note: {w}")

    totals = [r["total"] for r in runs]
    print(f"\nTotal time: mean {statistics.mean(totals):.2f}s, "
          f"min {min(totals):.2f}s, max {max(totals):.2f}s")
    print(f"Hosts found (last run): {runs[-1]['hosts']}, with web service: {runs[-1]['web']}")

    if args.compare:
        from app.adapters.external import ReconError, run_external_recon

        print("\nComparing with Subfinder + HTTPx ...")
        start = time.perf_counter()
        try:
            ext = run_external_recon(domain)
        except ReconError as exc:
            print(f"  External tools unavailable: {exc}")
            return
        elapsed = time.perf_counter() - start
        theirs = {a["hostname"] for a in ext["assets"]}
        ours = runs[-1]["names"]
        print(f"  External: {elapsed:.2f}s, {len(theirs)} live hosts")
        print(f"  Built-in: {runs[-1]['total']:.2f}s, {len(ours)} hosts")
        print(f"  In both: {len(ours & theirs)}; only built-in: {len(ours - theirs)}; "
              f"only external: {len(theirs - ours)}")


if __name__ == "__main__":
    main()
