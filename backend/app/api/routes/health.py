from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from app.db.database import get_db
from app.schemas.stock import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify API and database connectivity
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthCheckResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        timestamp=datetime.now(),
        database=db_status,
        version="1.0.0"
    )


@router.get("/market-status")
def get_market_status():
    """
    Get current US stock market status

    Returns information about:
    - Whether market is currently open
    - Current time in Eastern Time
    - Market hours (open/close times)
    - If today is a holiday or weekend
    - If today is an early close day

    Useful for displaying market status in the frontend and
    understanding when data fetching occurs.
    """
    from app.utils.market_hours import get_market_status_info

    return get_market_status_info()
