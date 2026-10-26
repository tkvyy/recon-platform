from tests.conftest import login_headers


def test_invalid_domain_returns_422(client):
    h = login_headers(client)
    r = client.post("/scans", json={"domain": "example.com; ls"}, headers=h)
    assert r.status_code == 422


def test_unknown_scan_returns_404(client):
    h = login_headers(client)
    assert client.get("/scans/does-not-exist", headers=h).status_code == 404


def test_create_scan_queues_job_and_reuses_recent_one(client):
    h = login_headers(client)
    first = client.post("/scans", json={"domain": "Example.com"}, headers=h)
    assert first.status_code == 202
    assert first.json()["reused"] is False
    assert client.queued == [first.json()["job_id"]]

    again = client.post("/scans", json={"domain": "example.com"}, headers=h)
    assert again.json()["reused"] is True
    assert again.json()["job_id"] == first.json()["job_id"]

    forced = client.post("/scans", json={"domain": "example.com", "force": True}, headers=h)
    assert forced.json()["reused"] is False


def test_diff_unknown_scan_returns_404(client):
    h = login_headers(client)
    assert client.get("/scans/nope-1/diff/nope-2", headers=h).status_code == 404
