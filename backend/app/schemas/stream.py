from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StreamJobStartRequest(BaseModel):
    source_type: Literal["rtsp", "video_file"] = "rtsp"
    source_uri: str
    worker_count: int = Field(default=2, ge=1, le=8)
    sample_every_n_frames: int = Field(default=6, ge=1, le=60)
    confidence_threshold: float = Field(default=0.35, ge=0.1, le=0.95)
    max_frames: int | None = Field(default=None, ge=1)


class StreamJobResponse(BaseModel):
    id: int
    source_type: str
    source_uri: str
    status: str
    worker_count: int
    sample_every_n_frames: int
    confidence_threshold: float
    max_frames: int | None
    processed_frames: int
    enqueued_tasks: int
    processed_tasks: int
    error_message: str | None
    started_at: datetime
    ended_at: datetime | None
