from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.database import Base, SessionLocal, engine
from app.models import ScanJob
from app.tasks import process_scan
from app.validators import is_valid_domain, normalize_domain

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Attack Surface Recon Platform")


class ScanRequest(BaseModel):
    domain: str


@app.post("/scans", status_code=202)
def create_scan(req: ScanRequest):
    domain = normalize_domain(req.domain)
    if not is_valid_domain(domain):
        raise HTTPException(status_code=422, detail="Invalid domain")

    db = SessionLocal()
    try:
        job = ScanJob(target_domain=domain, status="QUEUED")
        db.add(job)
        db.commit()
        job_id = job.job_id
    finally:
        db.close()

    process_scan.delay(job_id)
    return {"job_id": job_id, "status": "QUEUED"}


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
