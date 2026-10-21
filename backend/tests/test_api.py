import pytest
from fastapi import HTTPException

from app import main


def test_invalid_domain_returns_422():
    with pytest.raises(HTTPException) as exc:
        main.create_scan(main.ScanRequest(domain="example.com; ls"))
    assert exc.value.status_code == 422


def test_unknown_job_returns_404():
    with pytest.raises(HTTPException) as exc:
        main.get_scan("does-not-exist")
    assert exc.value.status_code == 404
