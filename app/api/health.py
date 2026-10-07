"""Health-check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> dict:
    """Returns OK and verifies DB connectivity."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
