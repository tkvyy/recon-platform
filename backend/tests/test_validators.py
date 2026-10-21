from app.validators import is_valid_domain, normalize_domain


def test_accepts_normal_domain():
    assert is_valid_domain("example.com")
    assert is_valid_domain("sub.example.co.ke")


def test_rejects_injection_attempts():
    assert not is_valid_domain("example.com; ls")
    assert not is_valid_domain("example.com && whoami")
    assert not is_valid_domain("$(whoami).com")


def test_normalizes_case_and_whitespace():
    assert normalize_domain("  Example.COM ") == "example.com"
    assert is_valid_domain("  Example.COM ")
