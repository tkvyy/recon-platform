import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    job_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_domain = Column(String, nullable=False)
    status = Column(String, default="QUEUED")  # QUEUED, RUNNING, COMPLETED, FAILED
    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)
    raw_count = Column(Integer, default=0)
    error = Column(Text, nullable=True)

    subdomains = relationship(
        "Subdomain", back_populates="job", cascade="all, delete-orphan"
    )


class Subdomain(Base):
    __tablename__ = "subdomains"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("scan_jobs.job_id"))
    hostname = Column(String)
    ip_address = Column(String, nullable=True)
    ips = Column(JSON, default=list)
    cname = Column(JSON, default=list)
    scheme = Column(String, nullable=True)
    http_status = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    headers = Column(JSON, default=dict)
    redirect_url = Column(String, nullable=True)
    tech_stack = Column(JSON, default=list)
    sources = Column(JSON, default=list)

    job = relationship("ScanJob", back_populates="subdomains")
