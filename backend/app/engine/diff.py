"""Scan comparison (FR10): what was added, removed, or changed between two scans."""

# Fields compared for hosts present in both scans.
COMPARED_FIELDS = ("ips", "cname", "http_status", "title", "redirect_url", "tech_stack")


def _norm(value):
    """Order-insensitive comparison for list fields."""
    if isinstance(value, list):
        return sorted(value)
    return value


def diff_scans(old_assets: list[dict], new_assets: list[dict]) -> dict:
    """Compare two lists of asset dicts (as stored per scan).

    Returns {"added": [...], "removed": [...], "changed": [...], "unchanged": int}.
    Each "changed" item is {"hostname", "changes": {field: {"old", "new"}}}.
    """
    old = {a["hostname"]: a for a in old_assets}
    new = {a["hostname"]: a for a in new_assets}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))

    changed = []
    unchanged = 0
    for host in sorted(set(old) & set(new)):
        changes = {}
        for field in COMPARED_FIELDS:
            before, after = old[host].get(field), new[host].get(field)
            if _norm(before) != _norm(after):
                changes[field] = {"old": before, "new": after}
        if changes:
            changed.append({"hostname": host, "changes": changes})
        else:
            unchanged += 1

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }
