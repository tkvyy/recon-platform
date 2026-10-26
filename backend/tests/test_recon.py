import pytest

from app import recon


def test_run_recon_rejects_invalid_domain():
    with pytest.raises(ValueError):
        recon.run_recon("example.com; ls")


def test_run_recon_normalises_and_delegates(monkeypatch):
    seen = {}

    async def fake_scan(domain, config=None):
        seen["domain"] = domain
        return {"domain": domain, "raw_count": 0, "assets": [], "warnings": []}

    monkeypatch.setattr(recon, "scan_domain", fake_scan)
    out = recon.run_recon("  Example.COM ")
    assert seen["domain"] == "example.com"
    assert out["assets"] == []
