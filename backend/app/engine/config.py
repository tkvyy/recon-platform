"""Tunable limits for the built-in engine (NFR3: rate limiting / concurrency)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanConfig:
    dns_concurrency: int = 50      # simultaneous DNS lookups
    http_concurrency: int = 20     # simultaneous HTTP probes
    dns_timeout: float = 3.0       # seconds per DNS lookup
    http_timeout: float = 8.0      # seconds per HTTP request
    max_wordlist: int = 5000       # cap on brute-force candidates
    use_ct: bool = True            # certificate transparency lookup
    use_bruteforce: bool = True    # wordlist DNS brute force
    wildcard_probes: int = 3       # random labels used to detect wildcard DNS
