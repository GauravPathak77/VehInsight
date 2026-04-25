from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.models import StreamJob, VehicleAnalysis
from app.db.session import Base, engine, get_db
from app.schemas.analysis import (
    ColorInfo,
    VehicleAnalysisDetail,
    VehicleAnalysisListItem,
)
from app.schemas.stream import StreamJobResponse, StreamJobStartRequest
from app.services.pipeline_service import pipeline_manager

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    f"{settings.api_prefix}/analyses",
    response_model=list[VehicleAnalysisListItem],
)
def list_analyses(
    db: Session = Depends(get_db),
    job_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[VehicleAnalysisListItem]:
    query = select(VehicleAnalysis)
    if job_id is not None:
        query = query.where(VehicleAnalysis.job_id == job_id)
    query = query.order_by(VehicleAnalysis.created_at.desc()).limit(limit)
    rows = db.execute(query).scalars().all()
    return [
        VehicleAnalysisListItem(
            id=row.id,
            job_id=row.job_id,
            source_ref=row.source_ref,
            frame_index=row.frame_index,
            track_id=row.track_id,
            logo=row.logo,
            plate_number=row.plate_number,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get(
    f"{settings.api_prefix}/analyses/recent",
    response_model=list[VehicleAnalysisDetail],
)
def list_recent_analyses(
    db: Session = Depends(get_db),
    job_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[VehicleAnalysisDetail]:
    query = select(VehicleAnalysis)
    if job_id is not None:
        query = query.where(VehicleAnalysis.job_id == job_id)
    query = query.order_by(VehicleAnalysis.created_at.desc()).limit(limit)
    rows = db.execute(query).scalars().all()
    response: list[VehicleAnalysisDetail] = []
    for row in rows:
        response.append(
            VehicleAnalysisDetail(
                id=row.id,
                job_id=row.job_id,
                source_ref=row.source_ref,
                frame_index=row.frame_index,
                track_id=row.track_id,
                logo=row.logo,
                plate_number=row.plate_number,
                created_at=row.created_at,
                bbox=row.bbox,
                colors=[ColorInfo(**color) for color in row.colors],
                annotated_image_base64=row.annotated_image_base64,
            )
        )
    return response


@app.post(
    f"{settings.api_prefix}/stream-jobs/start",
    response_model=StreamJobResponse,
)
def start_stream_job(
    payload: StreamJobStartRequest,
    db: Session = Depends(get_db),
) -> StreamJobResponse:
    row = StreamJob(
        source_type=payload.source_type,
        source_uri=payload.source_uri,
        status="running",
        worker_count=payload.worker_count,
        sample_every_n_frames=payload.sample_every_n_frames,
        confidence_threshold=payload.confidence_threshold,
        max_frames=payload.max_frames,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        pipeline_manager.start_job(row.id)
    except Exception as exc:
        row.status = "failed"
        row.error_message = str(exc)
        db.add(row)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {exc}") from exc

    return StreamJobResponse(
        id=row.id,
        source_type=row.source_type,
        source_uri=row.source_uri,
        status=row.status,
        worker_count=row.worker_count,
        sample_every_n_frames=row.sample_every_n_frames,
        confidence_threshold=row.confidence_threshold,
        max_frames=row.max_frames,
        processed_frames=row.processed_frames,
        enqueued_tasks=row.enqueued_tasks,
        processed_tasks=row.processed_tasks,
        error_message=row.error_message,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


@app.post(
    f"{settings.api_prefix}/stream-jobs/{{job_id}}/stop",
    response_model=StreamJobResponse,
)
def stop_stream_job(job_id: int, db: Session = Depends(get_db)) -> StreamJobResponse:
    row = db.get(StreamJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    pipeline_manager.stop_job(job_id)
    db.refresh(row)
    runtime = pipeline_manager.get_runtime_stats(job_id)
    if runtime:
        row.processed_frames = runtime["processed_frames"]
        row.enqueued_tasks = runtime["enqueued_tasks"]
        row.processed_tasks = runtime["processed_tasks"]
        db.add(row)
        db.commit()
        db.refresh(row)
    return StreamJobResponse(
        id=row.id,
        source_type=row.source_type,
        source_uri=row.source_uri,
        status=row.status,
        worker_count=row.worker_count,
        sample_every_n_frames=row.sample_every_n_frames,
        confidence_threshold=row.confidence_threshold,
        max_frames=row.max_frames,
        processed_frames=row.processed_frames,
        enqueued_tasks=row.enqueued_tasks,
        processed_tasks=row.processed_tasks,
        error_message=row.error_message,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


@app.get(
    f"{settings.api_prefix}/stream-jobs/{{job_id}}",
    response_model=StreamJobResponse,
)
def get_stream_job(job_id: int, db: Session = Depends(get_db)) -> StreamJobResponse:
    row = db.get(StreamJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    runtime = pipeline_manager.get_runtime_stats(job_id)
    if runtime is not None:
        processed_frames = runtime["processed_frames"]
        enqueued_tasks = runtime["enqueued_tasks"]
        processed_tasks = runtime["processed_tasks"]
    else:
        processed_frames = row.processed_frames
        enqueued_tasks = row.enqueued_tasks
        processed_tasks = row.processed_tasks

    return StreamJobResponse(
        id=row.id,
        source_type=row.source_type,
        source_uri=row.source_uri,
        status=row.status,
        worker_count=row.worker_count,
        sample_every_n_frames=row.sample_every_n_frames,
        confidence_threshold=row.confidence_threshold,
        max_frames=row.max_frames,
        processed_frames=processed_frames,
        enqueued_tasks=enqueued_tasks,
        processed_tasks=processed_tasks,
        error_message=row.error_message,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )
