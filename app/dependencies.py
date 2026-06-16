from dataclasses import dataclass
from fastapi import Header, HTTPException, Depends
from redis import Redis
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal


# Redis client (singleton)
_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Get the Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
    return _redis_client


def get_db():
    """Yield a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass
class UserContext:
    user_id: str
    plan: str


def get_user_context(
    x_user_id: str = Header(None),
    x_user_plan: str = Header(None),
) -> UserContext:
    """
    Extract user context from headers injected by the api-gateway.
    Rejects requests without the required headers.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    if not x_user_plan:
        raise HTTPException(status_code=403, detail="No active subscription")

    return UserContext(user_id=x_user_id, plan=x_user_plan.lower())
