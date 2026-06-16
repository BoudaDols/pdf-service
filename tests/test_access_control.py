"""Tests for plan-based access control logic."""
from unittest.mock import MagicMock
from app.services.access_control import check_access, increment_daily_count, add_reading_time


def _mock_redis(count=0, time=0):
    redis = MagicMock()
    redis.get.side_effect = lambda key: str(count) if "count" in key else str(time)
    redis.pipeline.return_value = redis
    redis.incr.return_value = None
    redis.incrby.return_value = None
    redis.expire.return_value = None
    redis.execute.return_value = None
    return redis


class TestFreeplan:
    def test_free_user_first_pdf_allowed(self):
        redis = _mock_redis(count=0, time=0)
        allowed, reason = check_access(redis, "user-1", "free")
        assert allowed is True

    def test_free_user_second_pdf_denied(self):
        redis = _mock_redis(count=1, time=0)
        allowed, reason = check_access(redis, "user-1", "free")
        assert allowed is False
        assert "limit" in reason.lower()

    def test_free_user_time_exceeded_denied(self):
        redis = _mock_redis(count=0, time=1800)
        allowed, reason = check_access(redis, "user-1", "free")
        assert allowed is False
        assert "time" in reason.lower()

    def test_free_user_under_time_allowed(self):
        redis = _mock_redis(count=0, time=1799)
        allowed, reason = check_access(redis, "user-1", "free")
        assert allowed is True


class TestBasicPlan:
    def test_basic_first_pdf_allowed(self):
        redis = _mock_redis(count=0, time=0)
        allowed, reason = check_access(redis, "user-1", "basic")
        assert allowed is True

    def test_basic_second_pdf_denied(self):
        redis = _mock_redis(count=1, time=0)
        allowed, reason = check_access(redis, "user-1", "basic")
        assert allowed is False

    def test_basic_no_time_limit(self):
        redis = _mock_redis(count=0, time=99999)
        allowed, reason = check_access(redis, "user-1", "basic")
        assert allowed is True


class TestPremiumPlan:
    def test_premium_always_allowed(self):
        redis = _mock_redis(count=100, time=99999)
        allowed, reason = check_access(redis, "user-1", "premium")
        assert allowed is True


class TestNoPlan:
    def test_unknown_plan_denied(self):
        redis = _mock_redis()
        allowed, reason = check_access(redis, "user-1", "unknown")
        assert allowed is False

    def test_empty_plan_denied(self):
        redis = _mock_redis()
        allowed, reason = check_access(redis, "user-1", "")
        assert allowed is False


class TestCounters:
    def test_increment_daily_count(self):
        redis = MagicMock()
        redis.pipeline.return_value = redis
        increment_daily_count(redis, "user-1")
        redis.incr.assert_called_once()
        redis.expire.assert_called_once()

    def test_add_reading_time(self):
        redis = MagicMock()
        redis.pipeline.return_value = redis
        add_reading_time(redis, "user-1", 300)
        redis.incrby.assert_called_once()
