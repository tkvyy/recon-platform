from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import Base, SessionLocal, engine
from app.models import ScanJob
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
            "assets": [
                {
                    "hostname": s.hostname,
                    "ip_address": s.ip_address,
                    "http_status": s.http_status,
                    "tech_stack": s.tech_stack,
                }
                for s in job.subdomains
            ],
        }
    finally:
        db.close()
