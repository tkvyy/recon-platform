from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import Base, SessionLocal, engine
from app.engine.diff import diff_scans
from app.models import ScanJob, Subdomain
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


class ScanRequest(BaseModel):
    domain: str
    force: bool = False


def find_reusable_scan(db, domain: str):
    """A scan already in progress, or a completed one from the last 24h."""
    in_flight = (
        db.query(ScanJob)
        .filter(
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
            ScanJob.target_domain == domain,
            ScanJob.status == "COMPLETED",
            ScanJob.completed_at >= cutoff,
        )
        .order_by(ScanJob.completed_at.desc())
        .first()
    )


@app.post("/scans", status_code=202)
def create_scan(req: ScanRequest):
    domain = normalize_domain(req.domain)
    if not is_valid_domain(domain):
        raise HTTPException(status_code=422, detail="Invalid domain")

    db = SessionLocal()
    try:
        if not req.force:
            existing = find_reusable_scan(db, domain)
            if existing:
                return {
                    "job_id": existing.job_id,
                    "status": existing.status,
                    "reused": True,
                }

        job = ScanJob(target_domain=domain, status="QUEUED")
        db.add(job)
        db.commit()
        job_id = job.job_id
    finally:
        db.close()

    process_scan.delay(job_id)
    return {"job_id": job_id, "status": "QUEUED", "reused": False}


@app.get("/scans")
def list_scans(limit: int = 20):
    db = SessionLocal()
    try:
        jobs = (
            db.query(ScanJob)
            .order_by(ScanJob.created_at.desc())
            .limit(min(limit, 100))
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
    finally:
        db.close()


@app.get("/scans/{job_id}")
def get_scan(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(ScanJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        return {
            "job_id": job.job_id,
            "target_domain": job.target_domain,
            "status": job.status,
            "error": job.error,
            "raw_count": job.raw_count,
            "assets": [asset_to_dict(a) for a in job.subdomains],
        }
    finally:
        db.close()


@app.get("/scans/{old_id}/diff/{new_id}")
def diff_endpoint(old_id: str, new_id: str):
    """Compare two scans of the same target: added / removed / changed hosts."""
    db = SessionLocal()
    try:
        old, new = db.get(ScanJob, old_id), db.get(ScanJob, new_id)
        if old is None or new is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        if old.target_domain != new.target_domain:
            raise HTTPException(
                status_code=422, detail="Scans must be for the same target"
            )
        result = diff_scans(
            [asset_to_dict(a) for a in old.subdomains],
            [asset_to_dict(a) for a in new.subdomains],
        )
        return {"old": old_id, "new": new_id, "target_domain": new.target_domain, **result}
    finally:
        db.close()
