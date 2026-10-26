from app import auth
from tests.conftest import login_headers, register


def test_password_hash_roundtrip_and_salting():
    h1, h2 = auth.hash_password("secret-pass"), auth.hash_password("secret-pass")
    assert h1 != h2  # unique salt per hash
    assert "secret-pass" not in h1
    assert auth.verify_password("secret-pass", h1)
    assert not auth.verify_password("wrong-pass", h1)


def test_verify_password_rejects_malformed_hash():
    assert not auth.verify_password("x", "garbage")
    assert not auth.verify_password("x", "bcrypt$1$2$3$aa$bb")


def test_register_then_login(client):
    assert register(client).status_code == 201
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-1"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_register_normalises_email_and_rejects_duplicates(client):
    assert register(client, "A@Example.com").status_code == 201
    assert register(client, "a@example.com").status_code == 409


def test_register_validates_input(client):
    assert register(client, "not-an-email").status_code == 422
    assert register(client, "b@example.com", "short").status_code == 422
    assert register(client, "c@example.com", "x" * 200).status_code == 422


def test_login_failure_is_generic(client):
    register(client)
    wrong_pw = client.post("/auth/login", json={"email": "a@example.com", "password": "nope-nope-1"})
    no_user = client.post("/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()  # does not reveal which emails exist


def test_passwords_are_not_stored_in_plaintext(client):
    from app.models import User

    register(client)
    db = client.db_factory()
    stored = db.query(User).one().password_hash
    db.close()
    assert "correct-horse-1" not in stored and stored.startswith("scrypt$")


def test_me_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    h = login_headers(client)
    assert client.get("/auth/me", headers=h).json()["email"] == "a@example.com"


def test_logout_invalidates_token(client):
    h = login_headers(client)
    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/auth/me", headers=h).status_code == 401


def test_expired_session_is_rejected(client):
    from datetime import timedelta

    from app.models import AuthSession

    h = login_headers(client)
    db = client.db_factory()
    s = db.query(AuthSession).one()
    s.expires_at = auth.utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()
    assert client.get("/auth/me", headers=h).status_code == 401
