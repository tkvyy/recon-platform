import asyncio

import pytest

from app import tasks
from app.engine.pipeline import ScanCancelled, scan_domain
from app.models import ScanJob, User
from tests.conftest import login_headers


def make_job(client, email, status):
    db = client.db_factory()
    owner = db.query(User).filter(User.email == email).one()
    job = ScanJob(owner_id=owner.id, target_domain="example.com", status=status)
    db.add(job)
    db.commit()
    job_id = job.job_id
    db.close()
    return job_id


def status_of(client, job_id):
    db = client.db_factory()
    status = db.get(ScanJob, job_id).status
    db.close()
    return status


# ----------------------------------------------------------------- API
@pytest.mark.parametrize("state", ["QUEUED", "RUNNING"])
def test_owner_can_stop_a_waiting_or_running_scan(client, state):
    h = login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", state)
    r = client.post(f"/scans/{job}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert status_of(client, job) == "CANCELLED"


@pytest.mark.parametrize("state", ["COMPLETED", "FAILED", "CANCELLED"])
def test_cannot_stop_a_finished_scan(client, state):
    h = login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", state)
    assert client.post(f"/scans/{job}/cancel", headers=h).status_code == 409


def test_cannot_stop_another_users_scan(client):
    alice = login_headers(client, "alice@example.com")
    bob = login_headers(client, "bob@example.com")
    job = make_job(client, "alice@example.com", "RUNNING")
    assert client.post(f"/scans/{job}/cancel", headers=bob).status_code == 404
    assert status_of(client, job) == "RUNNING"  # untouched
    assert client.post(f"/scans/{job}/cancel", headers=alice).status_code == 200


def test_stop_requires_login(client):
    assert client.post("/scans/x/cancel").status_code == 401


def test_stopped_scan_can_be_deleted_and_is_not_reused(client):
    h = login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", "RUNNING")
    client.post(f"/scans/{job}/cancel", headers=h)
    again = client.post("/scans", json={"domain": "example.com"}, headers=h)
    assert again.json()["reused"] is False
    assert client.delete(f"/scans/{job}", headers=h).status_code == 204


# -------------------------------------------------------------- worker
def test_worker_skips_a_scan_stopped_while_queued(client, monkeypatch):
    h = login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", "QUEUED")
    client.post(f"/scans/{job}/cancel", headers=h)

    monkeypatch.setattr(tasks, "SessionLocal", client.db_factory)
    called = []
    monkeypatch.setattr(tasks, "run_recon", lambda *a, **k: called.append(1))
    tasks.process_scan(job)
    assert called == []  # never started
    assert status_of(client, job) == "CANCELLED"


def test_worker_discards_results_when_stopped_mid_scan(client, monkeypatch):
    login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", "QUEUED")
    monkeypatch.setattr(tasks, "SessionLocal", client.db_factory)

    def fake_run(domain, should_cancel=None):
        # the user presses Stop while the engine is working
        db = client.db_factory()
        db.get(ScanJob, job).status = "CANCELLED"
        db.commit()
        db.close()
        assert should_cancel() is True
        return {"raw_count": 1, "warnings": [],
                "assets": [{"hostname": "a.example.com", "ip_address": "1.1.1.1"}]}

    monkeypatch.setattr(tasks, "run_recon", fake_run)
    tasks.process_scan(job)
    db = client.db_factory()
    j = db.get(ScanJob, job)
    assert j.status == "CANCELLED" and j.subdomains == []
    db.close()


def test_worker_still_completes_normal_scans(client, monkeypatch):
    login_headers(client, "a@example.com")
    job = make_job(client, "a@example.com", "QUEUED")
    monkeypatch.setattr(tasks, "SessionLocal", client.db_factory)
    monkeypatch.setattr(
        tasks, "run_recon",
        lambda domain, should_cancel=None: {
            "raw_count": 1, "warnings": [],
            "assets": [{"hostname": "a.example.com", "ip_address": "1.1.1.1"}],
        },
    )
    tasks.process_scan(job)
    assert status_of(client, job) == "COMPLETED"


# -------------------------------------------------------------- engine
def test_pipeline_raises_when_cancelled_before_start():
    async def lookup(name):
        return {"ips": ["1.1.1.1"], "cnames": []}

    async def ct(domain, client):
        return set()

    async def go():
        return await scan_domain(
            "example.com", lookup=lookup, ct_fetch=ct, wordlist=["www"],
            should_cancel=lambda: True,
        )

    with pytest.raises(ScanCancelled):
        asyncio.run(go())


def test_pipeline_stops_midway_when_cancel_flips():
    flag = {"stop": False}
    looked_up = []

    async def lookup(name):
        looked_up.append(name)
        flag["stop"] = True          # user presses Stop during DNS
        await asyncio.sleep(1.3)     # long enough for the 1s watcher to notice
        return {"ips": ["1.1.1.1"], "cnames": []}

    async def ct(domain, client):
        return set()

    words = [f"w{i}" for i in range(40)]

    async def go():
        from app.engine.config import ScanConfig
        return await scan_domain(
            "example.com", ScanConfig(dns_concurrency=2), lookup=lookup,
            ct_fetch=ct, wordlist=words, should_cancel=lambda: flag["stop"],
        )

    with pytest.raises(ScanCancelled):
        asyncio.run(go())
    assert len(looked_up) < 41  # it did not grind through every name
