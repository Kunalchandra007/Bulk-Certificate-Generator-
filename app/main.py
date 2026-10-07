"""App factory with lifespan for table creation and crash recovery."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.database import Base, engine
from app.errors import register_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create tables + run crash recovery. Shutdown: nothing special."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created.")

    # Recovery will be wired in Phase 6
    logger.info("Startup recovery: checking for interrupted jobs...")
    _run_startup_recovery()
    logger.info("Startup recovery complete.")

    yield  # app runs here


def _run_startup_recovery() -> None:
    """Re-queue jobs stuck in PROCESSING/PENDING from a previous crash."""
    # BackgroundTasks is not available here, so we could spawn threads,
    # but for simplicity since we don't have celery, we'll use threading.
    # In a real app we'd push them back to the queue broker.
    import threading

    from app.database import SessionLocal
    from app.models import Job, JobStatus, Recipient, RecipientStatus
    from app.services.processor import process_job

    with SessionLocal() as db:
        interrupted_jobs = (
            db.query(Job).filter(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])).all()
        )
        for job in interrupted_jobs:
            logger.info("Recovering interrupted job %s", job.id)

            # Reset PROCESSING recipients back to PENDING
            stuck_recipients = (
                db.query(Recipient)
                .filter(Recipient.job_id == job.id, Recipient.status == RecipientStatus.PROCESSING)
                .all()
            )
            for r in stuck_recipients:
                r.status = RecipientStatus.PENDING
            db.commit()

            # Re-queue the job in a background thread
            t = threading.Thread(target=process_job, args=(job.id, SessionLocal))
            t.start()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="Bulk Certificate Generator",
        description="Submit recipients in bulk, generate PDF certificates, track progress, and download.",
        version="1.0.0",
        lifespan=lifespan,
    )
    from app.api.retrieval import router as retrieval_router

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(retrieval_router)
    return app


app = create_app()
