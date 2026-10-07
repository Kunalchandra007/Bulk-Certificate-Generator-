"""Background job processor.

Processes recipients sequentially, wrapping each in a try/except so failures
don't stop the job. Commits after each recipient to make progress live.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.models import Job, JobStatus, Recipient, RecipientStatus
from app.services.certificate_renderer import CertificateData, render_certificate
from app.services.job_service import recompute_job_counts
from app.services.storage import storage

logger = logging.getLogger(__name__)


def generate_certificate_number(date_str: str) -> str:
    """Format: CERT-{YYYY}-{8 hex chars}"""
    year = date_str[:4] if date_str else datetime.now(timezone.utc).strftime("%Y")
    hex_str = secrets.token_hex(4).upper()  # 4 bytes = 8 hex chars
    return f"CERT-{year}-{hex_str}"


def process_job(job_id: uuid.UUID, session_factory: sessionmaker) -> None:
    """Background task to process a job.

    Opens its own DB session.
    Sets job to PROCESSING.
    For each PENDING recipient:
      - set PROCESSING
      - generate cert
      - if success: set SUCCESS, update file_path + cert number
      - if error: set FAILED, update error message
      - commit (so progress is live)
    Finally, recompute job counts to determine final status.
    """
    logger.info("process_job started for job_id=%s", job_id)
    with session_factory() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error("Job %s not found in processor", job_id)
            return

        if job.status == JobStatus.PENDING:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # Fetch only PENDING recipients (idempotent if resumed)
        recipients = (
            db.query(Recipient)
            .filter(Recipient.job_id == job_id, Recipient.status == RecipientStatus.PENDING)
            .order_by(Recipient.index)
            .all()
        )

        for r in recipients:
            r.status = RecipientStatus.PROCESSING
            db.commit()

            try:
                cert_num = generate_certificate_number(str(job.issue_date))

                data = CertificateData(
                    recipient_name=r.name,
                    job_title=job.title,
                    issuer_name=job.issuer_name,
                    issue_date=str(job.issue_date),
                    certificate_number=cert_num,
                    extra=r.extra,
                )

                out_path = storage.get_path(str(job.id), cert_num)
                render_certificate(data, out_path)

                # Success
                r.certificate_number = cert_num
                r.file_path = storage.get_relative_path(str(job.id), cert_num)
                r.status = RecipientStatus.SUCCESS
                r.error = None

                logger.info("Job %s Recipient %d SUCCESS: %s", job.id, r.index, cert_num)

            except Exception as e:
                # Failure: store error, but continue the loop
                r.status = RecipientStatus.FAILED
                error_msg = f"{e.__class__.__name__}: {str(e)}"
                # Truncate to 300 chars to avoid DB bloat or leaking massive traces
                r.error = error_msg[:300]
                logger.exception("Job %s Recipient %d FAILED", job.id, r.index)

            # Commit after EVERY recipient so progress is visible live
            db.commit()

        # Job finished: recompute totals and final status
        recompute_job_counts(job_id, db)
        logger.info("process_job finished for job_id=%s", job_id)
