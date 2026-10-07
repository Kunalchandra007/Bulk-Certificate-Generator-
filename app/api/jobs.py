"""Job API endpoints.

Route handlers stay thin: parse -> call service -> return.
"""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db, get_session_factory
from app.errors import ValidationError
from app.models import JobStatus
from app.schemas import (
    ErrorResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobLinks,
)
from app.services.job_service import create_job, has_valid_recipients

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post(
    "/",
    status_code=202,
    response_model=JobCreateResponse,
    responses={
        200: {"model": JobCreateResponse, "description": "Idempotency hit — existing job returned"},
        422: {"model": ErrorResponse, "description": "Request-level validation error"},
    },
)
def create_job_endpoint(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    session_factory=Depends(get_session_factory),
):
    """Submit a bulk certificate generation job.

    Returns 202 Accepted with the job ID. If an Idempotency-Key header is
    provided and a job with that key already exists, returns 200 with the
    existing job.
    """
    # Request-level: max recipients
    from app.config import settings

    if len(request.recipients) > settings.MAX_RECIPIENTS_PER_JOB:
        raise ValidationError(
            f"Too many recipients: {len(request.recipients)} "
            f"(max {settings.MAX_RECIPIENTS_PER_JOB})"
        )

    job = create_job(request, idempotency_key, db)

    # Determine if this was an idempotency hit
    is_existing = idempotency_key and job.idempotency_key == idempotency_key
    # Check if job was just created (no started_at) vs already existed
    # A simple heuristic: if the job has recipients that are pending, it's new or resumable
    if is_existing and job.status != JobStatus.PENDING:
        # Already existed — return 200
        links = _build_links(job.id)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=200,
            content=JobCreateResponse(
                id=job.id,
                status=job.status.value,
                total_count=job.total_count,
                success_count=job.success_count,
                failed_count=job.failed_count,
                links=links,
            ).model_dump(mode="json", by_alias=True),
        )

    # Schedule background processing if there are valid recipients
    if has_valid_recipients(job):
        from app.services.processor import process_job

        background_tasks.add_task(process_job, job.id, session_factory)

    links = _build_links(job.id)
    return JobCreateResponse(
        id=job.id,
        status=job.status.value,
        total_count=job.total_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        links=links,
    )


def _build_links(job_id: uuid.UUID) -> JobLinks:
    return JobLinks(
        **{
            "self": f"/api/jobs/{job_id}/",
            "certificates": f"/api/jobs/{job_id}/certificates/",
            "download": f"/api/jobs/{job_id}/download/",
        }
    )
