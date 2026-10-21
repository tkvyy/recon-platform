import re

# Letters, digits and hyphens only, dot-separated, no spaces or symbols.
DOMAIN_REGEX = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def normalize_domain(raw: str) -> str:
    """Trim whitespace and lowercase the domain."""
    return raw.strip().lower()


def is_valid_domain(raw: str) -> bool:
    """Return True only for a clean domain like 'example.com'."""
    return bool(DOMAIN_REGEX.match(normalize_domain(raw)))