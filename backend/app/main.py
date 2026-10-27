from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import auth
from app.database import Base, engine, get_db
from app.engine.diff import diff_scans
from app.models import ScanJob, Subdomain, User
from app.tasks import process_scan
from app.validators import is_valid_domain, normalize_domain

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Attack Surface Recon Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REUSE_WINDOW = timedelta(hours=24)


# ---------------------------------------------------------------- schemas
class Credentials(BaseModel):
    email: str
    password: str


class ScanRequest(BaseModel):
    domain: str
    force: bool = False


# ---------------------------------------------------------------- helpers
def asset_to_dict(s: Subdomain) -> dict:
    return {
        "hostname": s.hostname,
        "ip_address": s.ip_address,
        "ips": s.ips or [],
        "cname": s.cname or [],
        "scheme": s.scheme,
        "http_status": s.http_status,
        "title": s.title,
        "headers": s.headers or {},
        "redirect_url": s.redirect_url,
        "tech_stack": s.tech_stack or [],
        "sources": s.sources or [],
    }


def get_owned_scan(db: Session, job_id: str, user: User) -> ScanJob:
    """Fetch a scan only if it belongs to `user`.

    A scan owned by someone else returns the same 404 as a scan that does not
    exist, so IDs cannot be probed (FR2, NFR2).
    """
    job = (
        db.query(ScanJob)
        .filter(ScanJob.job_id == job_id, ScanJob.owner_id == user.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return job


def find_reusable_scan(db: Session, domain: str, user: User):
    """This user's scan in progress, or a completed one from the last 24h."""
    in_flight = (
        db.query(ScanJob)
        .filter(
            ScanJob.owner_id == user.id,
            ScanJob.target_domain == domain,
            ScanJob.status.in_(["QUEUED", "RUNNING"]),
        )
        .first()
    )
    if in_flight:
        return in_flight

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - REUSE_WINDOW
    return (
        db.query(ScanJob)
        .filter(
            ScanJob.owner_id == user.id,
            ScanJob.target_domain == domain,
            ScanJob.status == "COMPLETED",
            ScanJob.completed_at >= cutoff,
        )
        .order_by(ScanJob.completed_at.desc())
        .first()
    )


# ------------------------------------------------------------------- auth
@app.post("/auth/register", status_code=201)
def register(creds: Credentials, db: Session = Depends(get_db)):
    email = auth.validate_credentials(creds.email, creds.password)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=auth.hash_password(creds.password))
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email}


@app.post("/auth/login")
def login(creds: Credentials, db: Session = Depends(get_db)):
    user = auth.authenticate(db, creds.email, creds.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": auth.create_session(db, user), "token_type": "bearer"}


@app.post("/auth/logout", status_code=204)
def logout(
    authorization: str | None = Header(default=None),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    auth.revoke_token(db, authorization)
    return Response(status_code=204)


@app.get("/auth/me")
def me(user: User = Depends(auth.get_current_user)):
    return {"id": user.id, "email": user.email}


# ------------------------------------------------------------------ scans
@app.post("/scans", status_code=202)
def create_scan(
    req: ScanRequest,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    domain = normalize_domain(req.domain)
    if not is_valid_domain(domain):
        raise HTTPException(status_code=422, detail="Invalid domain")

    if not req.force:
        existing = find_reusable_scan(db, domain, user)
        if existing:
            return {
                "job_id": existing.job_id,
                "status": existing.status,
                "reused": True,
            }

    job = ScanJob(owner_id=user.id, target_domain=domain, status="QUEUED")
    db.add(job)
    db.commit()
    job_id = job.job_id

    process_scan.delay(job_id)
    return {"job_id": job_id, "status": "QUEUED", "reused": False}


@app.get("/scans")
def list_scans(
    limit: int = 20,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(ScanJob)
        .filter(ScanJob.owner_id == user.id)
        .order_by(ScanJob.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [
        {
            "job_id": j.job_id,
            "target_domain": j.target_domain,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "raw_count": j.raw_count,
            "live_count": len(j.subdomains),
        }
        for j in jobs
    ]


@app.get("/scans/{job_id}")
def get_scan(
    job_id: str,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    job = get_owned_scan(db, job_id, user)
    return {
        "job_id": job.job_id,
        "target_domain": job.target_domain,
        "status": job.status,
        "error": job.error,
        "raw_count": job.raw_count,
        "assets": [asset_to_dict(a) for a in job.subdomains],
    }


@app.post("/scans/{job_id}/cancel")
def cancel_scan(
    job_id: str,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Stop a scan that is waiting or running. The worker notices within seconds."""
    job = get_owned_scan(db, job_id, user)
    if job.status not in ("QUEUED", "RUNNING"):
        raise HTTPException(status_code=409, detail="This scan has already finished")
    job.status = "CANCELLED"
    job.error = None
    job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"job_id": job.job_id, "status": job.status}


@app.delete("/scans/{job_id}", status_code=204)
def delete_scan(
    job_id: str,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    job = get_owned_scan(db, job_id, user)
    if job.status in ("QUEUED", "RUNNING"):
        raise HTTPException(status_code=409, detail="Scan is still in progress")
    db.delete(job)
    db.commit()
    return Response(status_code=204)


@app.get("/scans/{old_id}/diff/{new_id}")
def diff_endpoint(
    old_id: str,
    new_id: str,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Compare two of your scans of the same target: added / removed / changed."""
    old = get_owned_scan(db, old_id, user)
    new = get_owned_scan(db, new_id, user)
    if old.target_domain != new.target_domain:
        raise HTTPException(status_code=422, detail="Scans must be for the same target")
    result = diff_scans(
        [asset_to_dict(a) for a in old.subdomains],
        [asset_to_dict(a) for a in new.subdomains],
    )
    return {"old": old_id, "new": new_id, "target_domain": new.target_domain, **result}
