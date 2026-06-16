from datetime import date
from redis import Redis

# Daily limits per plan
PLAN_LIMITS = {
    "free": {"max_pdfs": 1, "max_seconds": 1800},     # 1 PDF, 30 minutes
    "basic": {"max_pdfs": 1, "max_seconds": None},    # 1 PDF, unlimited time
    "premium": {"max_pdfs": None, "max_seconds": None},  # unlimited
}


def _daily_count_key(user_id: str) -> str:
    return f"pdf:daily_count:{user_id}:{date.today().isoformat()}"


def _daily_time_key(user_id: str) -> str:
    return f"pdf:daily_time:{user_id}:{date.today().isoformat()}"


def check_access(redis: Redis, user_id: str, plan: str) -> tuple[bool, str]:
    """
    Check if the user is allowed to open a PDF based on their plan.
    Returns (allowed: bool, reason: str).
    """
    limits = PLAN_LIMITS.get(plan)

    if not limits:
        return False, "No active subscription"

    # Premium — always allowed
    if limits["max_pdfs"] is None:
        return True, "OK"

    # Check daily PDF count
    count_key = _daily_count_key(user_id)
    current_count = int(redis.get(count_key) or 0)

    if current_count >= limits["max_pdfs"]:
        return False, "Daily PDF limit reached"

    # Free plan — also check reading time
    if limits["max_seconds"] is not None:
        time_key = _daily_time_key(user_id)
        current_time = int(redis.get(time_key) or 0)

        if current_time >= limits["max_seconds"]:
            return False, "Daily reading time exceeded (30 minutes)"

    return True, "OK"


def increment_daily_count(redis: Redis, user_id: str) -> None:
    """Increment the daily PDF open counter. Expires at end of day."""
    key = _daily_count_key(user_id)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)  # 24 hours TTL
    pipe.execute()


def add_reading_time(redis: Redis, user_id: str, seconds: int) -> None:
    """Add reading time to the daily total. Expires at end of day."""
    key = _daily_time_key(user_id)
    pipe = redis.pipeline()
    pipe.incrby(key, seconds)
    pipe.expire(key, 86400)  # 24 hours TTL
    pipe.execute()
