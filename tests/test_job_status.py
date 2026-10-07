"""Tests for job status tracking and progress."""

from app.models import JobStatus, RecipientStatus


def _valid_payload():
    return {
        "title": "Python Bootcamp",
        "issuer_name": "Acme",
        "issue_date": "2026-10-01",
        "recipients": [{"name": f"Person {i}", "email": f"p{i}@example.com"} for i in range(5)],
    }


def test_job_progress_and_completion(client, db_session, monkeypatch):
    """Test that counts are updated correctly.
    We monkeypatch the renderer to record state mid-run to assert PROCESSING status.
    """
    from app.services import processor

    original_render = processor.render_certificate

    mid_run_state = {}

    def _mock_render(data, out_path):
        # On the 3rd recipient (index 2), we capture the job state directly from DB
        if "Person 2" in data.recipient_name:
            from app.models import Job, Recipient

            job = db_session.query(Job).first()
            recs = db_session.query(Recipient).all()
            mid_run_state["status"] = job.status
            mid_run_state["success_count"] = sum(
                1 for r in recs if r.status == RecipientStatus.SUCCESS
            )

        # Then call actual renderer
        original_render(data, out_path)

    monkeypatch.setattr(processor, "render_certificate", _mock_render)

    resp = client.post("/api/jobs/", json=_valid_payload())
    assert resp.status_code == 202

    # The test client runs BackgroundTasks synchronously, so processing is done now.
    import uuid

    from app.models import Job

    job_id = uuid.UUID(resp.json()["id"])
    job = db_session.query(Job).filter(Job.id == job_id).first()

    # Assert mid-run state
    assert mid_run_state["status"] == JobStatus.PROCESSING
    # Before rendering 3rd recipient, 2 should be SUCCESS
    assert mid_run_state["success_count"] == 2

    # Assert final state
    assert job.status == JobStatus.COMPLETED
    assert job.total_count == 5
    assert job.success_count == 5
    assert job.failed_count == 0
