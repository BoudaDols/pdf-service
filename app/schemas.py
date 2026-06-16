from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PdfOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    filename: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class SessionOpenResponse(BaseModel):
    success: bool = True
    message: str = "Reading session started"
    url: str
    session_id: str


class SessionCloseResponse(BaseModel):
    success: bool = True
    message: str = "Reading session ended"
    duration_seconds: int


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
