from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Pdf(Base):
    __tablename__ = "pdfs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)  # S3 key or blob name
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    pdf_id = Column(Integer, ForeignKey("pdfs.id"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    plan_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
