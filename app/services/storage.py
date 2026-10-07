"""Storage abstraction for generated certificates.

Currently uses the local filesystem under STORAGE_DIR.
Wrapped in a class so it can be swapped to S3 with minimal changes.
"""

from pathlib import Path

from app.config import settings


class FileStorage:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or settings.STORAGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_path(self, job_id: str, certificate_number: str) -> Path:
        """Get the absolute path for a certificate PDF."""
        # Sanitize just to be safe, though these are generated UUIDs/hex
        safe_job = "".join(c for c in str(job_id) if c.isalnum() or c in "-_")
        safe_cert = "".join(c for c in certificate_number if c.isalnum() or c in "-_")

        job_dir = self.base_dir / safe_job
        job_dir.mkdir(exist_ok=True)
        return job_dir / f"{safe_cert}.pdf"

    def exists(self, job_id: str, certificate_number: str) -> bool:
        """Check if a certificate PDF exists on disk."""
        return self.get_path(job_id, certificate_number).exists()

    def get_relative_path(self, job_id: str, certificate_number: str) -> str:
        """Get the path relative to STORAGE_DIR to store in the DB."""
        safe_job = "".join(c for c in str(job_id) if c.isalnum() or c in "-_")
        safe_cert = "".join(c for c in certificate_number if c.isalnum() or c in "-_")
        return f"{safe_job}/{safe_cert}.pdf"


storage = FileStorage()
