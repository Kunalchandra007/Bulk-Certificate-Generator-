"""Tests for startup crash recovery."""

from datetime import date

from app.models import Job, JobStatus, Recipient, RecipientStatus


def test_startup_recovery(db_session, monkeypatch):
    """Test that a stuck job is resumed."""
    # 1. Setup a "stuck" job
    job = Job(
        title="Crash Test",
        issuer_name="Acme",
        issue_date=date(2026, 10, 1),
        status=JobStatus.PROCESSING,
        total_count=3,
        success_count=1,
        failed_count=0,
    )
    db_session.add(job)
    db_session.flush()

    # Recipient 1: SUCCESS already
    r1 = Recipient(
        job_id=job.id,
        index=0,
        name="A",
        email="a@a.com",
        status=RecipientStatus.SUCCESS,
        certificate_number="C-1",
    )
    # Recipient 2: stuck in PROCESSING (crashed while generating)
    r2 = Recipient(
        job_id=job.id, index=1, name="B", email="b@b.com", status=RecipientStatus.PROCESSING
    )
    # Recipient 3: PENDING
    r3 = Recipient(
        job_id=job.id, index=2, name="C", email="c@c.com", status=RecipientStatus.PENDING
    )

    db_session.add_all([r1, r2, r3])
    db_session.commit()

    # 2. Mock threading.Thread to run the function inline synchronously
    import threading

    class InlineThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(threading, "Thread", InlineThread)

    # 3. Inject our test db_session into SessionLocal for recovery
    from sqlalchemy.orm import sessionmaker

    TestingSessionLocal = sessionmaker(
        bind=db_session.get_bind(), autocommit=False, autoflush=False
    )

    import app.database

    monkeypatch.setattr(app.database, "SessionLocal", TestingSessionLocal)

    # 4. Trigger recovery
    app.main._run_startup_recovery()

    # 5. Assert final state
    db_session.refresh(job)
    assert job.status == JobStatus.COMPLETED
    assert job.success_count == 3

    db_session.refresh(r2)
    assert r2.status == RecipientStatus.SUCCESS
    assert r2.certificate_number is not None
