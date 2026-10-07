"""Job service: create jobs, query jobs, recompute status/counts."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Job, JobStatus, Recipient, RecipientStatus
from app.schemas import JobCreateRequest
from app.services.validation import validate_recipients

logger = logging.getLogger(__name__)


def create_job(
    request: JobCreateRequest,
    idempotency_key: str | None,
    db: Session,
) -> Job:
    """Create a new job with all recipient rows.

    - Validates each recipient individually (bad ones get status FAILED).
    - Batch-inserts with session.add_all in one transaction.
    - If zero valid recipients, marks job FAILED immediately.

    Returns the Job ORM object (attached to the session).
    """
    # Check idempotency key first
    if idempotency_key:
        existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
        if existing:
            logger.info(
                "Idempotency hit for key=%s, returning job=%s", idempotency_key, existing.id
            )
            return existing

    # Validate recipients
    validated = validate_recipients(request.recipients)

    # Build the job
    job = Job(
        title=request.title.strip(),
        issuer_name=request.issuer_name.strip(),
        issue_date=request.issue_date,
        idempotency_key=idempotency_key,
        total_count=len(validated),
    )

    # Build recipient rows
    recipients: list[Recipient] = []
    failed_count = 0
    for idx, v in enumerate(validated):
        status = RecipientStatus.FAILED if v["error"] else RecipientStatus.PENDING
        if v["error"]:
            failed_count += 1
        recipients.append(
            Recipient(
                index=idx,
                name=v["name"],
                email=v["email"],
                extra=v["extra"],
                status=status,
                error=v["error"],
            )
        )

    job.failed_count = failed_count
    valid_count = len(validated) - failed_count

    # If zero valid recipients, mark job FAILED immediately
    if valid_count == 0:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        logger.info("Job %s: all %d recipients invalid, marking FAILED", job.id, len(validated))

    db.add(job)
    db.flush()  # ensure job.id is available for FK references

    # Now create recipients with the flushed job.id
    for r in recipients:
        r.job_id = job.id

    db.add_all(recipients)
    db.commit()
    db.refresh(job)

    return job


def get_job_by_id(job_id: uuid.UUID, db: Session) -> Job | None:
    """Fetch a job by its UUID primary key."""
    return db.query(Job).filter(Job.id == job_id).first()


def has_valid_recipients(job: Job) -> bool:
    """Check whether the job has at least one PENDING recipient."""
    return any(r.status == RecipientStatus.PENDING for r in job.recipients)


def recompute_job_counts(job_id: uuid.UUID, db: Session) -> Job:
    """Recompute success/failed/total counts from recipient rows (not incremented blindly).

    Also sets the final job status: all success -> COMPLETED,
    some failed -> COMPLETED_WITH_ERRORS, all failed -> FAILED.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")

    recipients = db.query(Recipient).filter(Recipient.job_id == job_id).all()

    success = sum(1 for r in recipients if r.status == RecipientStatus.SUCCESS)
    failed = sum(1 for r in recipients if r.status == RecipientStatus.FAILED)

    job.total_count = len(recipients)
    job.success_count = success
    job.failed_count = failed

    # Determine final status
    if success == len(recipients):
        job.status = JobStatus.COMPLETED
    elif failed == len(recipients):
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.COMPLETED_WITH_ERRORS

    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
