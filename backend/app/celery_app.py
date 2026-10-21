from celery import Celery

celery_app = Celery(
    "recon",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=["app.tasks"],
)
