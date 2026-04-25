import os
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import cv2
from ultralytics import YOLO

from app.core.config import settings
from app.db.models import StreamJob, VehicleAnalysis
from app.db.session import SessionLocal
from app.services.image_service import annotate_image
from app.services.vision_service import VisionAnalysisService

VEHICLE_CLASS_IDS = {2, 3, 5, 7}


@dataclass
class RuntimeJob:
    stop_event: threading.Event
    task_queue: queue.Queue
    worker_count: int
    producer_thread: threading.Thread | None = None
    worker_threads: list[threading.Thread] = field(default_factory=list)
    stats_lock: threading.Lock = field(default_factory=threading.Lock)
    processed_frames: int = 0
    enqueued_tasks: int = 0
    processed_tasks: int = 0

    def incr(self, field_name: str, amount: int = 1) -> None:
        with self.stats_lock:
            current = getattr(self, field_name)
            setattr(self, field_name, current + amount)

    def snapshot(self) -> dict[str, int]:
        with self.stats_lock:
            return {
                "processed_frames": self.processed_frames,
                "enqueued_tasks": self.enqueued_tasks,
                "processed_tasks": self.processed_tasks,
            }


class StreamPipelineManager:
    def __init__(self) -> None:
        self.model = YOLO(settings.yolo_model_path)
        self.vision_service = VisionAnalysisService()
        self._jobs: dict[int, RuntimeJob] = {}
        self._lock = threading.Lock()

    def start_job(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(StreamJob, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} does not exist.")
        finally:
            db.close()

        runtime = RuntimeJob(
            stop_event=threading.Event(),
            task_queue=queue.Queue(maxsize=settings.queue_max_size),
            worker_count=job.worker_count,
        )
        with self._lock:
            self._jobs[job_id] = runtime

        producer = threading.Thread(
            target=self._producer_loop,
            args=(job_id,),
            daemon=True,
            name=f"producer-{job_id}",
        )
        runtime.producer_thread = producer
        producer.start()

        for index in range(job.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(job_id,),
                daemon=True,
                name=f"worker-{job_id}-{index}",
            )
            runtime.worker_threads.append(worker)
            worker.start()

    def stop_job(self, job_id: int) -> None:
        runtime = self._jobs.get(job_id)
        if runtime is None:
            return
        runtime.stop_event.set()
        for _ in range(runtime.worker_count):
            try:
                runtime.task_queue.put_nowait(None)
            except queue.Full:
                break
        self._mark_job_status(job_id, status="stopped")

    def get_runtime_stats(self, job_id: int) -> dict[str, int] | None:
        runtime = self._jobs.get(job_id)
        if runtime is None:
            return None
        return runtime.snapshot()

    def _producer_loop(self, job_id: int) -> None:
        runtime = self._jobs[job_id]
        db = SessionLocal()
        cap = None
        try:
            job = db.get(StreamJob, job_id)
            if job is None:
                return

            source_uri = job.source_uri
            if job.source_type == "video_file" and not os.path.exists(source_uri):
                raise RuntimeError(f"Video file not found: {source_uri}")

            cap = cv2.VideoCapture(source_uri)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open source: {source_uri}")

            frame_index = 0
            while not runtime.stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_index += 1
                runtime.incr("processed_frames")

                if job.max_frames and frame_index > job.max_frames:
                    break
                if frame_index % job.sample_every_n_frames != 0:
                    continue

                detections = self._extract_vehicle_detections(
                    frame=frame,
                    confidence_threshold=job.confidence_threshold,
                )
                for det in detections:
                    x1, y1, x2, y2 = det["bbox"].values()
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    success, encoded = cv2.imencode(".jpg", crop)
                    if not success:
                        continue
                    task = {
                        "job_id": job_id,
                        "source_ref": source_uri,
                        "frame_index": frame_index,
                        "track_id": det["track_id"],
                        "bbox": det["bbox"],
                        "crop_bytes": encoded.tobytes(),
                    }
                    while not runtime.stop_event.is_set():
                        try:
                            runtime.task_queue.put(task, timeout=0.5)
                            runtime.incr("enqueued_tasks")
                            break
                        except queue.Full:
                            continue

            if runtime.stop_event.is_set():
                self._mark_job_status(job_id, status="stopped")
            else:
                self._mark_job_status(job_id, status="completed")
        except Exception as exc:
            self._mark_job_status(job_id, status="failed", error_message=str(exc))
        finally:
            if cap is not None:
                cap.release()
            for _ in range(runtime.worker_count):
                try:
                    runtime.task_queue.put_nowait(None)
                except queue.Full:
                    pass
            db.close()

    def _worker_loop(self, job_id: int) -> None:
        runtime = self._jobs[job_id]
        db = SessionLocal()
        try:
            while not runtime.stop_event.is_set():
                try:
                    task = runtime.task_queue.get(timeout=1)
                except queue.Empty:
                    producer_alive = (
                        runtime.producer_thread.is_alive()
                        if runtime.producer_thread is not None
                        else False
                    )
                    if not producer_alive and runtime.task_queue.empty():
                        break
                    continue

                if task is None:
                    runtime.task_queue.task_done()
                    break

                try:
                    crop_bytes = task["crop_bytes"]
                    logo = self.vision_service.detect_logo(crop_bytes)
                    plate_number = self.vision_service.detect_plate_number(crop_bytes)
                    colors = self.vision_service.detect_colors(crop_bytes)
                    normalized_colors = [
                        {
                            "name": color["name"],
                            "rgb": list(color["rgb"]),
                            "confidence": color["confidence"],
                        }
                        for color in colors
                    ]
                    annotated = annotate_image(crop_bytes, logo, plate_number, normalized_colors)

                    row = VehicleAnalysis(
                        job_id=task["job_id"],
                        source_ref=task["source_ref"],
                        frame_index=task["frame_index"],
                        track_id=task["track_id"],
                        bbox=task["bbox"],
                        logo=logo,
                        plate_number=plate_number,
                        colors=normalized_colors,
                        annotated_image_base64=annotated,
                    )
                    db.add(row)
                    db.commit()
                    runtime.incr("processed_tasks")
                except Exception:
                    db.rollback()
                finally:
                    runtime.task_queue.task_done()
        finally:
            db.close()
            self._sync_job_counters(job_id, runtime.snapshot())
            if runtime.producer_thread and not runtime.producer_thread.is_alive():
                with self._lock:
                    if job_id in self._jobs:
                        del self._jobs[job_id]

    def _extract_vehicle_detections(
        self,
        frame: Any,
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        results = self.model.track(
            frame,
            persist=True,
            conf=confidence_threshold,
            classes=list(VEHICLE_CLASS_IDS),
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.xyxy is None:
            return []

        xyxy = boxes.xyxy.cpu().tolist()
        classes = boxes.cls.int().cpu().tolist()
        ids = (
            boxes.id.int().cpu().tolist()
            if boxes.id is not None
            else [None for _ in range(len(xyxy))]
        )

        frame_height, frame_width = frame.shape[:2]
        detections: list[dict[str, Any]] = []
        for box, class_id, track_id in zip(xyxy, classes, ids):
            if class_id not in VEHICLE_CLASS_IDS:
                continue
            x1, y1, x2, y2 = [int(value) for value in box]
            x1 = max(0, min(x1, frame_width - 1))
            y1 = max(0, min(y1, frame_height - 1))
            x2 = max(1, min(x2, frame_width))
            y2 = max(1, min(y2, frame_height))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                {
                    "track_id": track_id,
                    "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                }
            )
        return detections

    @staticmethod
    def _mark_job_status(job_id: int, status: str, error_message: str | None = None) -> None:
        db = SessionLocal()
        try:
            job = db.get(StreamJob, job_id)
            if job is None:
                return
            job.status = status
            job.error_message = error_message
            if status in {"completed", "stopped", "failed"}:
                job.ended_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _sync_job_counters(job_id: int, counters: dict[str, int]) -> None:
        db = SessionLocal()
        try:
            job = db.get(StreamJob, job_id)
            if job is None:
                return
            job.processed_frames = counters["processed_frames"]
            job.enqueued_tasks = counters["enqueued_tasks"]
            job.processed_tasks = counters["processed_tasks"]
            db.commit()
        finally:
            db.close()


pipeline_manager = StreamPipelineManager()
