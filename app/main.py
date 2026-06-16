import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from redis import Redis

from app.database import create_tables
from app.models import Pdf
from app.schemas import PdfOut, SessionOpenResponse, SessionCloseResponse, ErrorResponse
from app.dependencies import get_db, get_redis, get_user_context, UserContext
from app.services.session import open_session, close_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: nothing special."""
    logger.info("Creating database tables...")
    create_tables()
    logger.info("pdf-service ready")
    yield


app = FastAPI(
    title="PDF Service",
    description="PDF access control based on subscription plan",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── PDF Catalog ───────────────────────────────────────────────────────────────

@app.get("/pdfs", response_model=list[PdfOut])
def list_pdfs(db: Session = Depends(get_db)):
    """List all available PDFs."""
    return db.query(Pdf).all()


@app.get("/pdfs/{pdf_id}", response_model=PdfOut)
def get_pdf(pdf_id: int, db: Session = Depends(get_db)):
    """Get metadata for a specific PDF."""
    pdf = db.query(Pdf).filter(Pdf.id == pdf_id).first()
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    return pdf


# ── Reading Sessions ──────────────────────────────────────────────────────────

@app.post(
    "/pdfs/{pdf_id}/open",
    response_model=SessionOpenResponse,
    responses={403: {"model": ErrorResponse}},
)
def open_pdf(
    pdf_id: int,
    user: UserContext = Depends(get_user_context),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
):
    """
    Open a reading session for a PDF.
    Checks plan limits, increments daily counter, returns a pre-signed download URL.
    """
    # Verify PDF exists
    pdf = db.query(Pdf).filter(Pdf.id == pdf_id).first()
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")

    success, result = open_session(redis, db, user.user_id, pdf.id, user.plan, pdf.filename)

    if not success:
        raise HTTPException(status_code=403, detail=result["message"])

    return SessionOpenResponse(url=result["url"], session_id=result["session_id"])


@app.post(
    "/pdfs/{pdf_id}/close",
    response_model=SessionCloseResponse,
    responses={400: {"model": ErrorResponse}},
)
def close_pdf(
    pdf_id: int,
    user: UserContext = Depends(get_user_context),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
):
    """
    Close a reading session.
    Calculates duration, persists to MySQL, updates daily reading time in Redis.
    """
    success, result = close_session(redis, db, user.user_id)

    if not success:
        raise HTTPException(status_code=400, detail=result["message"])

    return SessionCloseResponse(duration_seconds=result["duration_seconds"])
