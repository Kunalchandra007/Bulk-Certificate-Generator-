"""Tests for POST /api/jobs/ — job creation, links, and idempotency."""


def _valid_payload(**overrides):
    """Helper to build a valid request body with optional overrides."""
    payload = {
        "title": "Python Bootcamp 2026",
        "issuer_name": "Acme Academy",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Bob Smith", "email": "bob@example.com"},
        ],
    }
    payload.update(overrides)
    return payload


def test_valid_job_returns_202_with_id(client):
    resp = client.post("/api/jobs/", json=_valid_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert "id" in body
    assert body["status"] == "PENDING"
    assert body["total_count"] == 2
    assert body["success_count"] == 0


def test_job_and_recipient_rows_created(client, db_session):
    resp = client.post("/api/jobs/", json=_valid_payload())
    import uuid

    job_id = uuid.UUID(resp.json()["id"])

    from app.models import Job, Recipient

    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert job.title == "Python Bootcamp 2026"

    recipients = db_session.query(Recipient).filter(Recipient.job_id == job_id).all()
    assert len(recipients) == 2


def test_links_present_in_response(client):
    resp = client.post("/api/jobs/", json=_valid_payload())
    body = resp.json()
    links = body["links"]
    assert "self" in links
    assert "certificates" in links
    assert "download" in links
    assert body["id"] in links["self"]


def test_idempotency_key_returns_same_job(client):
    payload = _valid_payload()
    headers = {"Idempotency-Key": "unique-key-123"}

    resp1 = client.post("/api/jobs/", json=payload, headers=headers)
    resp2 = client.post("/api/jobs/", json=payload, headers=headers)

    assert resp1.json()["id"] == resp2.json()["id"]


def test_idempotency_key_different_keys_create_different_jobs(client):
    payload = _valid_payload()
    resp1 = client.post("/api/jobs/", json=payload, headers={"Idempotency-Key": "key-a"})
    resp2 = client.post("/api/jobs/", json=payload, headers={"Idempotency-Key": "key-b"})
    assert resp1.json()["id"] != resp2.json()["id"]
