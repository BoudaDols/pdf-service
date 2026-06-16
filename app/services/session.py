import json
import uuid
from datetime import datetime, timezone
from redis import Redis
from sqlalchemy.orm import Session
from app.models import ReadingSession
from app.services import access_control
from app.services.storage import get_presigned_url


def _session_key(user_id: str) -> str:
    return f"pdf:session:{user_id}"


def open_session(
    redis: Redis, db: Session, user_id: str, pdf_id: int, plan: str, filename: str
) -> tuple[bool, dict]:
    """
    Open a reading session.
    Returns (success, data_or_error).
    """
    # Check if user already has an active session
    existing = redis.get(_session_key(user_id))
    if existing:
        return False, {"message": "You already have an active reading session. Close it first."}

    # Check access limits
    allowed, reason = access_control.check_access(redis, user_id, plan)
    if not allowed:
        return False, {"message": reason}

    # Generate pre-signed URL
    url = get_presigned_url(filename)

    # Create session in Redis
    session_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "pdf_id": pdf_id,
        "plan": plan,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    redis.setex(_session_key(user_id), 3600, json.dumps(session_data))  # 1h TTL

    # Increment daily PDF counter
    access_control.increment_daily_count(redis, user_id)

    return True, {"url": url, "session_id": session_id}


def close_session(redis: Redis, db: Session, user_id: str) -> tuple[bool, dict]:
    """
    Close a reading session.
    Calculates duration, persists to MySQL, updates daily time in Redis.
    Returns (success, data_or_error).
    """
    session_raw = redis.get(_session_key(user_id))
    if not session_raw:
        return False, {"message": "No active reading session found"}

    session_data = json.loads(session_raw)
    started_at = datetime.fromisoformat(session_data["started_at"])
    ended_at = datetime.now(timezone.utc)
    duration = int((ended_at - started_at).total_seconds())

    # Persist to MySQL
    reading_session = ReadingSession(
        user_id=user_id,
        pdf_id=session_data["pdf_id"],
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration,
        plan_type=session_data["plan"],
    )
    db.add(reading_session)
    db.commit()

    # Update daily reading time in Redis (for free plan enforcement)
    access_control.add_reading_time(redis, user_id, duration)

    # Clear the active session
    redis.delete(_session_key(user_id))

    return True, {"duration_seconds": duration}
