"""Integration tests for the FastAPI endpoints."""
import os
from unittest.mock import patch, MagicMock

# Set test env before importing app
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PASSWORD"] = "test"
os.environ["REDIS_HOST"] = "localhost"
os.environ["STORAGE_BACKEND"] = "s3"
os.environ["S3_BUCKET"] = "test-bucket"

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db, get_redis
from app.models import Pdf


# Mock DB session
def _mock_db():
    db = MagicMock()
    # Return a fake PDF for queries
    fake_pdf = Pdf(id=1, title="Test PDF", filename="test.pdf", description="A test")
    db.query.return_value.all.return_value = [fake_pdf]
    db.query.return_value.filter.return_value.first.return_value = fake_pdf
    yield db


# Mock Redis
def _mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.pipeline.return_value = redis
    redis.incr.return_value = None
    redis.incrby.return_value = None
    redis.expire.return_value = None
    redis.execute.return_value = None
    redis.setex.return_value = None
    return redis


app.dependency_overrides[get_db] = _mock_db
app.dependency_overrides[get_redis] = _mock_redis

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPdfCatalog:
    def test_list_pdfs(self):
        response = client.get("/pdfs", headers={"X-User-ID": "u1", "X-User-Plan": "free"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_pdf(self):
        response = client.get("/pdfs/1", headers={"X-User-ID": "u1", "X-User-Plan": "free"})
        assert response.status_code == 200
        assert response.json()["title"] == "Test PDF"


class TestOpenPdf:
    @patch("app.services.session.get_presigned_url", return_value="https://example.com/test.pdf")
    def test_open_pdf_premium_allowed(self, mock_url):
        response = client.post(
            "/pdfs/1/open",
            headers={"X-User-ID": "user-1", "X-User-Plan": "premium"},
        )
        assert response.status_code == 200
        assert "url" in response.json()

    def test_open_pdf_no_user_id_rejected(self):
        response = client.post("/pdfs/1/open", headers={"X-User-Plan": "free"})
        assert response.status_code == 401

    def test_open_pdf_no_plan_rejected(self):
        response = client.post("/pdfs/1/open", headers={"X-User-ID": "user-1"})
        assert response.status_code == 403


class TestClosePdf:
    def test_close_pdf_no_session_returns_400(self):
        response = client.post(
            "/pdfs/1/close",
            headers={"X-User-ID": "user-1", "X-User-Plan": "free"},
        )
        assert response.status_code == 400
