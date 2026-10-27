from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import SessionLocal
from app.engine.pipeline import ScanCancelled
from app.models import ScanJob, Subdomain
from app.recon import run_recon


def _is_cancelled(job_id: str) -> bool:
    """Fresh short-lived session, so we always see the user's latest action."""
    db = SessionLocal()
    try:
        job = db.get(ScanJob, job_id)
        return job is None or job.status == "CANCELLED"
    finally:
        db.close()


@celery_app.task(name="recon.process_scan")
def process_scan(job_id: str) -> None:
    """Background worker: recon -> parse -> save."""
    db = SessionLocal()
    try:
        job = db.get(ScanJob, job_id)
        # Stopped (or deleted) while it was still waiting in the queue.
        if job is None or job.status == "CANCELLED":
            return
        job.status = "RUNNING"
        db.commit()

        try:
            result = run_recon(
                job.target_domain, should_cancel=lambda: _is_cancelled(job_id)
            )
        except ScanCancelled:
            return  # status was already set to CANCELLED by the API

        db.refresh(job)
        if job.status == "CANCELLED":
            return  # stopped just as it finished; discard the results
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
        if job is not None and job.status != "CANCELLED":
            job.status = "FAILED"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
