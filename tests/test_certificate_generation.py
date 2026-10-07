"""Tests for PDF rendering and storage."""

from app.services.certificate_renderer import CertificateData, render_certificate


def test_certificate_render_creates_file_and_starts_with_pdf(tmp_path):
    out_path = tmp_path / "cert.pdf"
    data = CertificateData(
        recipient_name="Asha Rao",
        job_title="Python Bootcamp",
        issuer_name="Acme Academy",
        issue_date="2026-10-01",
        certificate_number="CERT-1234",
        extra="Distinction",
    )

    render_certificate(data, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0

    with open(out_path, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_certificate_render_unicode_name(tmp_path):
    out_path = tmp_path / "cert_unicode.pdf"
    data = CertificateData(
        recipient_name="José Ordoñez 漢字",
        job_title="Test",
        issuer_name="Acme",
        issue_date="2026-10-01",
        certificate_number="CERT-000",
        extra=None,
    )

    # Should not raise exception
    render_certificate(data, out_path)
    assert out_path.exists()


def test_certificate_render_long_name_does_not_crash(tmp_path):
    out_path = tmp_path / "cert_long.pdf"
    data = CertificateData(
        recipient_name="A" * 60,  # Very long name to trigger font shrink
        job_title="Test",
        issuer_name="Acme",
        issue_date="2026-10-01",
        certificate_number="CERT-000",
        extra=None,
    )

    render_certificate(data, out_path)
    assert out_path.exists()


def test_certificate_render_90char_name_with_spaces(tmp_path):
    """A 90-character name with spaces triggers two-line word-wrap."""
    long_name = "Bartholomew Alexander Maximilian Christopherson Worthington III Esquire of Canterbury"
    # Pad to exactly 90 chars
    long_name = long_name.ljust(90)[:90]
    out_path = tmp_path / "cert_90_spaces.pdf"
    data = CertificateData(
        recipient_name=long_name,
        job_title="Test",
        issuer_name="Acme",
        issue_date="2026-10-01",
        certificate_number="CERT-WRAP-1",
        extra=None,
    )

    render_certificate(data, out_path)
    assert out_path.exists()

    with open(out_path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_certificate_render_90char_name_no_spaces(tmp_path):
    """A 90-character name with no spaces triggers character-width split."""
    out_path = tmp_path / "cert_90_nospace.pdf"
    data = CertificateData(
        recipient_name="A" * 90,
        job_title="Test",
        issuer_name="Acme",
        issue_date="2026-10-01",
        certificate_number="CERT-WRAP-2",
        extra=None,
    )

    # Must not raise
    render_certificate(data, out_path)
    assert out_path.exists()

    with open(out_path, "rb") as f:
        assert f.read(4) == b"%PDF"
