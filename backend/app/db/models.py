from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StreamJob(Base):
    __tablename__ = "stream_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_uri: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    worker_count: Mapped[int] = mapped_column(Integer, default=2)
    sample_every_n_frames: Mapped[int] = mapped_column(Integer, default=6)
    confidence_threshold: Mapped[float] = mapped_column(default=0.35)
    max_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_frames: Mapped[int] = mapped_column(Integer, default=0)
    enqueued_tasks: Mapped[int] = mapped_column(Integer, default=0)
    processed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VehicleAnalysis(Base):
    __tablename__ = "vehicle_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("stream_jobs.id"), index=True)
    source_ref: Mapped[str] = mapped_column(Text)
    frame_index: Mapped[int] = mapped_column(Integer, index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bbox: Mapped[dict] = mapped_column(JSON)
    logo: Mapped[str] = mapped_column(String(255))
    plate_number: Mapped[str] = mapped_column(String(255))
    colors: Mapped[list[dict]] = mapped_column(JSON)
    annotated_image_base64: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
