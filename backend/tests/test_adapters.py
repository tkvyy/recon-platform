import pytest

from app.adapters import external as recon


def test_subfinder_dedups_lowercases_and_sorts(monkeypatch):
    out = "B.example.com\na.example.com\nb.example.com\n\n"
    monkeypatch.setattr(recon, "_run", lambda cmd, input_text=None, timeout=300: out)
    assert recon.run_subfinder("example.com") == ["a.example.com", "b.example.com"]


def test_httpx_parses_json_and_skips_noise(monkeypatch):
    out = (
        '{"input":"a.example.com","host_ip":"1.2.3.4","status_code":200,"tech":["Nginx"]}\n'
        "not json\n"
    )
    monkeypatch.setattr(recon, "_run", lambda cmd, input_text=None, timeout=300: out)
    assert recon.run_httpx(["a.example.com"]) == [
        {
            "hostname": "a.example.com",
            "ip_address": "1.2.3.4",
            "http_status": 200,
            "tech_stack": ["Nginx"],
        }
    ]


def test_httpx_with_no_hosts_returns_empty():
    assert recon.run_httpx([]) == []


def test_missing_tool_raises_recon_error(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(recon.subprocess, "run", boom)
    with pytest.raises(recon.ReconError):
        recon.run_subfinder("example.com")
