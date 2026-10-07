"""Tests for input validation — both request-level (422) and recipient-level (FAILED rows)."""


def _valid_payload(**overrides):
    payload = {
        "title": "Python Bootcamp 2026",
        "issuer_name": "Acme Academy",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Asha Rao", "email": "asha@example.com"},
        ],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Request-level validation (should return 422, rejecting the whole request)
# ---------------------------------------------------------------------------


def test_empty_recipients_422(client):
    resp = client.post("/api/jobs/", json=_valid_payload(recipients=[]))
    assert resp.status_code == 422


def test_missing_title_422(client):
    payload = _valid_payload()
    del payload["title"]
    resp = client.post("/api/jobs/", json=payload)
    assert resp.status_code == 422


def test_blank_title_422(client):
    resp = client.post("/api/jobs/", json=_valid_payload(title=""))
    assert resp.status_code == 422


def test_missing_issuer_422(client):
    payload = _valid_payload()
    del payload["issuer_name"]
    resp = client.post("/api/jobs/", json=payload)
    assert resp.status_code == 422


def test_bad_date_422(client):
    resp = client.post("/api/jobs/", json=_valid_payload(issue_date="not-a-date"))
    assert resp.status_code == 422


def test_over_limit_recipients_422(client):
    """More recipients than MAX_RECIPIENTS_PER_JOB should 422."""
    from app.config import settings

    original = settings.MAX_RECIPIENTS_PER_JOB
    settings.MAX_RECIPIENTS_PER_JOB = 2  # temporarily lower the limit

    recipients = [{"name": f"Person {i}", "email": f"p{i}@example.com"} for i in range(3)]
    resp = client.post("/api/jobs/", json=_valid_payload(recipients=recipients))
    assert resp.status_code == 422

    settings.MAX_RECIPIENTS_PER_JOB = original


def test_title_too_long_422(client):
    resp = client.post("/api/jobs/", json=_valid_payload(title="A" * 201))
    assert resp.status_code == 422


def test_issuer_too_long_422(client):
    resp = client.post("/api/jobs/", json=_valid_payload(issuer_name="B" * 201))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Recipient-level validation (invalid recipient stored as FAILED, valid ones proceed)
# ---------------------------------------------------------------------------


def test_invalid_recipient_stored_as_failed(client, db_session):
    """A blank-name recipient should be stored with status FAILED and a clear error."""
    payload = _valid_payload(
        recipients=[
            {"name": "Valid Person", "email": "valid@example.com"},
            {"name": "", "email": "bad-email"},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    assert resp.status_code == 202

    import uuid

    job_id = uuid.UUID(resp.json()["id"])
    from app.models import Recipient, RecipientStatus

    recipients = (
        db_session.query(Recipient)
        .filter(Recipient.job_id == job_id)
        .order_by(Recipient.index)
        .all()
    )
    # First recipient should be SUCCESS (valid)
    assert recipients[0].status == RecipientStatus.SUCCESS
    assert recipients[0].error is None

    # Second recipient should be FAILED with error
    assert recipients[1].status == RecipientStatus.FAILED
    assert "name is required" in recipients[1].error


def test_bad_email_stored_as_failed(client, db_session):
    payload = _valid_payload(
        recipients=[
            {"name": "Good Name", "email": "not-an-email"},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    import uuid

    job_id = uuid.UUID(resp.json()["id"])

    from app.models import Recipient

    r = db_session.query(Recipient).filter(Recipient.job_id == job_id).first()
    assert r.error is not None
    assert "invalid email" in r.error


def test_duplicate_email_case_insensitive(client, db_session):
    """Second occurrence of same email (case-insensitive) should be FAILED."""
    payload = _valid_payload(
        recipients=[
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "ALICE@example.com"},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    import uuid

    job_id = uuid.UUID(resp.json()["id"])

    from app.models import Recipient, RecipientStatus

    recipients = (
        db_session.query(Recipient)
        .filter(Recipient.job_id == job_id)
        .order_by(Recipient.index)
        .all()
    )
    assert recipients[0].status == RecipientStatus.SUCCESS
    assert recipients[1].status == RecipientStatus.FAILED
    assert "duplicate email" in recipients[1].error
    assert "index 0" in recipients[1].error


def test_all_invalid_recipients_job_status_failed(client, db_session):
    """If zero recipients are valid, job is marked FAILED immediately."""
    payload = _valid_payload(
        recipients=[
            {"name": "", "email": "bad"},
            {"name": "", "email": "worse"},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    assert resp.status_code == 202

    import uuid

    job_id = uuid.UUID(resp.json()["id"])
    from app.models import Job, JobStatus

    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job.status == JobStatus.FAILED


def test_extra_too_long_stored_as_failed(client, db_session):
    payload = _valid_payload(
        recipients=[
            {"name": "Valid", "email": "v@example.com", "extra": "X" * 101},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    import uuid

    job_id = uuid.UUID(resp.json()["id"])

    from app.models import Recipient

    r = db_session.query(Recipient).filter(Recipient.job_id == job_id).first()
    assert "extra must be at most 100 characters" in r.error


def test_valid_recipients_proceed_despite_invalid_ones(client):
    """The response should show failed_count for invalid ones, total_count for all."""
    payload = _valid_payload(
        recipients=[
            {"name": "Good", "email": "good@example.com"},
            {"name": "", "email": "bad"},
        ]
    )
    resp = client.post("/api/jobs/", json=payload)
    body = resp.json()
    assert body["total_count"] == 2
    assert body["failed_count"] == 1
