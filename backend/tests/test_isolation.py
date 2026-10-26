"""NFR2 / FR2: no user can read, compare, list, or delete another user's scans."""
import pytest

from app.models import ScanJob, Subdomain, User
from tests.conftest import login_headers


def make_scan(client, owner_email, domain="example.com", status="COMPLETED", hosts=("a.example.com",)):
    db = client.db_factory()
    owner = db.query(User).filter(User.email == owner_email).one()
    job = ScanJob(owner_id=owner.id, target_domain=domain, status=status)
    job.completed_at = __import__("app.auth", fromlist=["utcnow"]).utcnow()
    db.add(job)
    db.flush()
    for h in hosts:
        db.add(Subdomain(job_id=job.job_id, hostname=h, ips=["1.1.1.1"], cname=[], tech_stack=[]))
    db.commit()
    job_id = job.job_id
    db.close()
    return job_id


@pytest.fixture
def two_users(client):
    alice = login_headers(client, "alice@example.com")
    bob = login_headers(client, "bob@example.com")
    return client, alice, bob


def test_every_scan_route_requires_login(client):
    for method, path in [
        ("get", "/scans"),
        ("post", "/scans"),
        ("get", "/scans/x"),
        ("delete", "/scans/x"),
        ("get", "/scans/x/diff/y"),
    ]:
        kwargs = {"json": {"domain": "example.com"}} if method == "post" else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401, path


def test_user_cannot_read_another_users_scan(two_users):
    client, alice, bob = two_users
    scan = make_scan(client, "alice@example.com")
    assert client.get(f"/scans/{scan}", headers=alice).status_code == 200
    assert client.get(f"/scans/{scan}", headers=bob).status_code == 404


def test_other_users_scan_looks_identical_to_missing_scan(two_users):
    client, alice, bob = two_users
    scan = make_scan(client, "alice@example.com")
    foreign = client.get(f"/scans/{scan}", headers=bob)
    missing = client.get("/scans/does-not-exist", headers=bob)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()  # existence is not leaked


def test_listing_only_shows_own_scans(two_users):
    client, alice, bob = two_users
    a_scan = make_scan(client, "alice@example.com")
    b_scan = make_scan(client, "bob@example.com", domain="other.org")
    a_ids = [s["job_id"] for s in client.get("/scans", headers=alice).json()]
    b_ids = [s["job_id"] for s in client.get("/scans", headers=bob).json()]
    assert a_ids == [a_scan]
    assert b_ids == [b_scan]


def test_user_cannot_delete_another_users_scan(two_users):
    client, alice, bob = two_users
    scan = make_scan(client, "alice@example.com")
    assert client.delete(f"/scans/{scan}", headers=bob).status_code == 404
    assert client.get(f"/scans/{scan}", headers=alice).status_code == 200  # still there
    assert client.delete(f"/scans/{scan}", headers=alice).status_code == 204
    assert client.get(f"/scans/{scan}", headers=alice).status_code == 404


def test_cannot_delete_scan_in_progress(two_users):
    client, alice, _ = two_users
    scan = make_scan(client, "alice@example.com", status="RUNNING")
    assert client.delete(f"/scans/{scan}", headers=alice).status_code == 409


def test_user_cannot_diff_against_another_users_scan(two_users):
    client, alice, bob = two_users
    a_scan = make_scan(client, "alice@example.com")
    b_scan = make_scan(client, "bob@example.com")
    # Bob tries both orders using Alice's scan ID
    assert client.get(f"/scans/{a_scan}/diff/{b_scan}", headers=bob).status_code == 404
    assert client.get(f"/scans/{b_scan}/diff/{a_scan}", headers=bob).status_code == 404


def test_own_scans_can_be_diffed(two_users):
    client, alice, _ = two_users
    old = make_scan(client, "alice@example.com", hosts=("a.example.com",))
    new = make_scan(client, "alice@example.com", hosts=("a.example.com", "b.example.com"))
    r = client.get(f"/scans/{old}/diff/{new}", headers=alice)
    assert r.status_code == 200
    assert r.json()["added"] == ["b.example.com"]


def test_cached_scans_are_not_shared_between_users(two_users):
    client, alice, bob = two_users
    a_scan = make_scan(client, "alice@example.com")  # fresh COMPLETED scan of example.com
    r = client.post("/scans", json={"domain": "example.com"}, headers=bob)
    assert r.json()["reused"] is False
    assert r.json()["job_id"] != a_scan


def test_scan_is_owned_by_the_creator(two_users):
    client, alice, bob = two_users
    job_id = client.post("/scans", json={"domain": "example.com"}, headers=alice).json()["job_id"]
    assert client.get(f"/scans/{job_id}", headers=alice).status_code == 200
    assert client.get(f"/scans/{job_id}", headers=bob).status_code == 404
