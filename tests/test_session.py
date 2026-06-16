"""Tests for reading session open/close logic."""
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.services.session import open_session, close_session


def _mock_redis(existing_session=None, count=0, time=0):
    redis = MagicMock()

    def get_side_effect(key):
        if "session" in key:
            return existing_session
        if "count" in key:
            return str(count)
        if "time" in key:
            return str(time)
        return None

    redis.get.side_effect = get_side_effect
    redis.setex.return_value = None
    redis.delete.return_value = None
    redis.pipeline.return_value = redis
    redis.incr.return_value = None
    redis.incrby.return_value = None
    redis.expire.return_value = None
    redis.execute.return_value = None
    return redis


class TestOpenSession:
    @patch("app.services.session.get_presigned_url", return_value="https://s3.example.com/file.pdf")
    def test_open_session_success(self, mock_url):
        redis = _mock_redis()
        db = MagicMock()

        success, result = open_session(redis, db, "user-1", 1, "premium", "file.pdf")

        assert success is True
        assert "url" in result
        assert "session_id" in result
        redis.setex.assert_called_once()

    def test_open_session_denied_existing_session(self):
        existing = json.dumps({"session_id": "abc", "pdf_id": 1, "plan": "free", "started_at": "2026-01-01T00:00:00+00:00"})
        redis = _mock_redis(existing_session=existing)
        db = MagicMock()

        success, result = open_session(redis, db, "user-1", 2, "free", "other.pdf")

        assert success is False
        assert "active" in result["message"].lower()

    @patch("app.services.session.get_presigned_url", return_value="https://s3.example.com/file.pdf")
    def test_open_session_denied_limit_reached(self, mock_url):
        redis = _mock_redis(count=1)
        db = MagicMock()

        success, result = open_session(redis, db, "user-1", 1, "free", "file.pdf")

        assert success is False
        assert "limit" in result["message"].lower()


class TestCloseSession:
    def test_close_session_success(self):
        started = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        session_data = json.dumps({"session_id": "abc", "pdf_id": 1, "plan": "free", "started_at": started})
        redis = _mock_redis(existing_session=session_data)
        # Override get to return the session for session key
        redis.get.side_effect = lambda key: session_data if "session" in key else "0"

        db = MagicMock()

        success, result = close_session(redis, db, "user-1")

        assert success is True
        assert result["duration_seconds"] >= 600  # ~10 minutes
        db.add.assert_called_once()
        db.commit.assert_called_once()
        redis.delete.assert_called_once()

    def test_close_session_no_active_session(self):
        redis = _mock_redis(existing_session=None)
        # Override get to return None for session key
        redis.get.return_value = None
        db = MagicMock()

        success, result = close_session(redis, db, "user-1")

        assert success is False
        assert "no active" in result["message"].lower()
