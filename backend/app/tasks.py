from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ScanJob, Subdomain
from app.recon import run_recon


@celery_app.task(name="recon.process_scan")
def process_scan(job_id: str) -> None:
    """Background worker: recon -> parse -> save."""
    db = SessionLocal()
    try:
        job = db.get(ScanJob, job_id)
        job.status = "RUNNING"
        db.commit()

        result = run_recon(job.target_domain)
        for asset in result["assets"]:
            db.add(Subdomain(job_id=job_id, **asset))
        job.raw_count = result["raw_count"]
        # Non-fatal notes (e.g. CT lookup failed, wildcard DNS) are kept visible.
        job.error = "; ".join(result.get("warnings", [])) or None
        job.status = "COMPLETED"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(ScanJob, job_id)
        job.status = "FAILED"
        job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
