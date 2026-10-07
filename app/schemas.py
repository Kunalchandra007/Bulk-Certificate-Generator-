"""Pydantic v2 request/response schemas with example payloads for OpenAPI docs."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RecipientIn(BaseModel):
    """Single recipient inside a job request.

    Declared leniently (all optional strings) so Pydantic does not reject the
    entire request body when one recipient is malformed. Real validation
    happens in services/validation.py.
    """

    name: str | None = None
    email: str | None = None
    extra: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Asha Rao", "email": "asha@example.com", "extra": "Distinction"}]
        }
    }


class JobCreateRequest(BaseModel):
    """Request body for POST /api/jobs/."""

    title: str = Field(..., min_length=1, max_length=200, examples=["Python Bootcamp 2026"])
    issuer_name: str = Field(..., min_length=1, max_length=200, examples=["Acme Academy"])
    issue_date: date = Field(..., examples=["2026-10-01"])
    recipients: list[RecipientIn] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobLinks(BaseModel):
    self_link: str = Field(..., alias="self")
    certificates: str
    download: str

    model_config = {"populate_by_name": True}


class JobCreateResponse(BaseModel):
    id: UUID
    status: str
    total_count: int
    success_count: int
    failed_count: int
    links: JobLinks

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: UUID
    title: str
    issuer_name: str
    issue_date: date
    status: str
    total_count: int
    success_count: int
    failed_count: int
    pending_count: int
    progress_percent: float
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecipientOut(BaseModel):
    id: UUID
    index: int
    name: str
    email: str
    status: str
    certificate_number: str | None = None
    error: str | None = None
    download_url: str | None = None

    model_config = {"from_attributes": True}


class CertificateListResponse(BaseModel):
    total: int
    items: list[RecipientOut]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
    code: str
