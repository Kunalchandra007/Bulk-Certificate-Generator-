"""Tests for individual failure handling during processing."""

from app.models import JobStatus, RecipientStatus


def _valid_payload():
    return {
        "title": "Python Bootcamp",
        "issuer_name": "Acme",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "BobFail", "email": "bob@example.com"},
            {"name": "Charlie", "email": "charlie@example.com"},
        ],
    }


def test_individual_failure_does_not_stop_job(client, db_session, monkeypatch):
    """Monkeypatch the renderer to raise for ONE specific recipient."""
    from app.services import processor

    original_render = processor.render_certificate

    def _mock_render(data, out_path):
        if data.recipient_name == "BobFail":
            raise ValueError("Simulated rendering failure")
        original_render(data, out_path)

    monkeypatch.setattr(processor, "render_certificate", _mock_render)

    resp = client.post("/api/jobs/", json=_valid_payload())
    assert resp.status_code == 202

    import uuid

    job_id = uuid.UUID(resp.json()["id"])

    from app.models import Job, Recipient

    job = db_session.query(Job).filter(Job.id == job_id).first()
    recipients = (
        db_session.query(Recipient)
        .filter(Recipient.job_id == job_id)
        .order_by(Recipient.index)
        .all()
    )

    # Bob should be FAILED
    assert recipients[1].status == RecipientStatus.FAILED
    assert "Simulated rendering failure" in recipients[1].error

    # Alice and Charlie should be SUCCESS
    assert recipients[0].status == RecipientStatus.SUCCESS
    assert recipients[2].status == RecipientStatus.SUCCESS

    # Job status should be COMPLETED_WITH_ERRORS
    assert job.status == JobStatus.COMPLETED_WITH_ERRORS
    assert job.total_count == 3
    assert job.success_count == 2
    assert job.failed_count == 1
