from celery import Celery

from app.core.config import settings

# The result backend needs to be prefixed with `db+` for SQLAlchemy.
# We construct it here to avoid issues with Pydantic settings interpolation.
celery_result_backend = f"db+{settings.DATABASE_URL}"

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=celery_result_backend,
    include=["app.worker"],  # Points to the file where tasks are defined
)

celery_app.conf.update(
    task_track_started=True,
)
