"""Per-recipient validation and duplicate detection.

Request-level validation (blank title, empty recipients, etc.) is handled
by Pydantic in schemas.py.  This module handles the *recipient-level*
validation that must NOT reject the whole request — invalid recipients are
stored with status FAILED and a clear error message.
"""

import re

from email_validator import EmailNotValidError, validate_email

from app.schemas import RecipientIn

# Precompiled for speed (though simple enough to inline)
_WHITESPACE_RE = re.compile(r"\s+")


def validate_recipients(
    recipients: list[RecipientIn],
) -> list[dict]:
    """Validate each recipient individually. Returns a list of dicts:
    {"name": str, "email": str, "extra": str|None, "error": str|None}

    Rules (from spec §5):
    - name: 1-100 chars after trimming whitespace; required
    - email: valid format via email-validator; required
    - duplicate email (case-insensitive) within the same job flags later duplicates
    - extra: max 100 chars
    """
    results: list[dict] = []
    seen_emails: dict[str, int] = {}  # normalized_email -> first index

    for idx, r in enumerate(recipients):
        errors: list[str] = []

        # --- Name ---
        raw_name = (r.name or "").strip()
        raw_name = _WHITESPACE_RE.sub(" ", raw_name)  # collapse internal whitespace
        if not raw_name:
            errors.append("name is required")
        elif len(raw_name) > 100:
            errors.append("name must be at most 100 characters")

        # --- Email ---
        raw_email = (r.email or "").strip()
        normalized_email: str | None = None
        if not raw_email:
            errors.append("email is required")
        else:
            try:
                info = validate_email(raw_email, check_deliverability=False)
                normalized_email = info.normalized.lower()
            except EmailNotValidError:
                errors.append("invalid email")

        # --- Duplicate email (only if email itself is valid) ---
        if normalized_email and not errors:
            if normalized_email in seen_emails:
                first = seen_emails[normalized_email]
                errors.append(f"duplicate email in this job (first seen at index {first})")
            else:
                seen_emails[normalized_email] = idx

        # --- Extra ---
        raw_extra = (r.extra or "").strip() or None
        if raw_extra and len(raw_extra) > 100:
            errors.append("extra must be at most 100 characters")

        results.append(
            {
                "name": raw_name or (r.name or ""),
                "email": raw_email or (r.email or ""),
                "extra": raw_extra,
                "error": "; ".join(errors) if errors else None,
            }
        )

    return results
