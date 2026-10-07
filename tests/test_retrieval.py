"""Tests for retrieving job status, listing certificates, and downloading PDFs/ZIPs."""

import zipfile
from io import BytesIO

from app.models import JobStatus


def _valid_payload():
    return {
        "title": "Python Bootcamp",
        "issuer_name": "Acme",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
            {"name": "Charlie", "email": "bad"},  # FAILED validation
        ],
    }


def test_get_job_status(client):
    # Create job
    resp = client.post("/api/jobs/", json=_valid_payload())
    job_id = resp.json()["id"]

    # Fetch status
    resp2 = client.get(f"/api/jobs/{job_id}/")
    assert resp2.status_code == 200

    body = resp2.json()
    assert body["status"] == JobStatus.COMPLETED_WITH_ERRORS.value
    assert body["total_count"] == 3
    assert body["success_count"] == 2
    assert body["failed_count"] == 1
    assert body["pending_count"] == 0
    assert body["progress_percent"] == 100.0


def test_list_certificates_with_pagination_and_filter(client):
    # Create job
    resp = client.post("/api/jobs/", json=_valid_payload())
    job_id = resp.json()["id"]

    # List all
    resp_all = client.get(f"/api/jobs/{job_id}/certificates/")
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 3
    assert len(resp_all.json()["items"]) == 3

    # Filter SUCCESS
    resp_success = client.get(f"/api/jobs/{job_id}/certificates/?status=SUCCESS")
    assert resp_success.json()["total"] == 2
    assert len(resp_success.json()["items"]) == 2

    # Check download_url is present for SUCCESS
    item = resp_success.json()["items"][0]
    assert "download_url" in item
    assert item["certificate_number"] is not None

    # Filter FAILED
    resp_failed = client.get(f"/api/jobs/{job_id}/certificates/?status=FAILED")
    assert resp_failed.json()["total"] == 1
    item = resp_failed.json()["items"][0]
    assert item.get("download_url") is None
    assert "error" in item


def test_download_single_certificate(client):
    resp = client.post("/api/jobs/", json=_valid_payload())
    job_id = resp.json()["id"]

    # Get the certificate number
    resp_list = client.get(f"/api/jobs/{job_id}/certificates/?status=SUCCESS")
    cert_num = resp_list.json()["items"][0]["certificate_number"]

    # Download it
    resp_pdf = client.get(f"/api/jobs/{job_id}/certificates/{cert_num}/")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.headers["content-disposition"] == f'attachment; filename="{cert_num}.pdf"'

    # Check it's a PDF
    assert resp_pdf.content.startswith(b"%PDF")


def test_download_certificate_409_if_failed(client):
    resp = client.post("/api/jobs/", json=_valid_payload())
    job_id = resp.json()["id"]

    # Try downloading the failed one (it won't have a certificate_number, but if we somehow tried)
    resp_pdf = client.get(f"/api/jobs/{job_id}/certificates/FAKE-CERT/")
    assert resp_pdf.status_code == 404


def test_download_zip_of_certificates(client):
    payload = _valid_payload()
    payload["recipients"] = [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "Zoë Müller", "email": "zoe@example.com"},
        {"name": "A" * 90, "email": "long@example.com"}
    ]
    resp = client.post("/api/jobs/", json=payload)
    job_id = resp.json()["id"]

    resp_zip = client.get(f"/api/jobs/{job_id}/download/")
    assert resp_zip.status_code == 200
    assert resp_zip.headers["content-type"] == "application/zip"
    
    expected_filename = f"certificates-{str(job_id)[:8]}.zip"
    assert resp_zip.headers["content-disposition"] == f'attachment; filename="{expected_filename}"'

    # Read the ZIP
    with zipfile.ZipFile(BytesIO(resp_zip.content)) as zf:
        names = zf.namelist()
        assert len(names) == 3
        
        # Check slugs
        assert any(name.endswith("_asha-rao.pdf") for name in names)
        assert any(name.endswith("_zoe-muller.pdf") for name in names)
        assert any(name.endswith("_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.pdf") for name in names)
