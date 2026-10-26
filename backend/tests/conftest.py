import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db


@pytest.fixture
def client(monkeypatch):
    """TestClient on a fresh in-memory database; the Celery queue is stubbed out."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    queued = []
    monkeypatch.setattr(main.process_scan, "delay", lambda job_id: queued.append(job_id))

    c = TestClient(main.app)
    c.db_factory = Session
    c.queued = queued
    yield c
    main.app.dependency_overrides.clear()


def register(client, email="a@example.com", password="correct-horse-1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def login_headers(client, email="a@example.com", password="correct-horse-1"):
    """Register (if needed) and log in; return Authorization headers."""
    register(client, email, password)
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
