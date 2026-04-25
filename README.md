# VehInsight

VehInsight is a real-time vehicle analytics platform that ingests RTSP/video streams, detects and tracks vehicles with YOLO, analyzes detected crops with Google Vision + OpenCV, and stores structured outputs in PostgreSQL.

- `backend/` - FastAPI orchestration API + stream processing pipeline
- `frontend/` - Next.js monitoring UI for stream job control and live results

## Overview

VehInsight now runs as a stream-first system (not single image upload). You provide an RTSP URL or video file path, then the backend starts a job that processes frames continuously:

Main workflow:

1. Frontend sends a stream job request (`rtsp` or `video_file`) to FastAPI.
2. OpenCV captures frames from the source.
3. YOLO detects and tracks vehicles (`car`, `motorcycle`, `bus`, `truck`).
4. Detected vehicle crops are pushed to an in-memory queue.
5. Worker threads consume the queue and run:
   - logo detection
   - OCR plate extraction
   - dominant color extraction
6. OpenCV creates annotated crop images for each processed detection.
7. Results are persisted in PostgreSQL and exposed via API for the frontend.

Key capabilities:

- Real-time stream ingestion from RTSP or local video files.
- YOLO-based vehicle detection + tracking across frames.
- Queue-driven multi-threaded processing for higher throughput.
- Google Vision + OpenCV enrichment for each tracked crop.
- PostgreSQL persistence for stream jobs and per-detection analysis rows.
- Live job status and recent result querying via FastAPI endpoints.

## Project Structure

```text
VehInsight/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── schemas/
│   │   │   └── analysis.py
│   │   │   └── stream.py
│   │   ├── services/
│   │   │   ├── image_service.py
│   │   │   ├── pipeline_service.py
│   │   │   └── vision_service.py
│   │   └── main.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.jsx
│   │   └── page.jsx
│   ├── .env.local.example
│   └── package.json
├── start.bat
├── .env
└── .env.example
```

## Backend Setup (FastAPI)

1. Create a virtual environment:

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:

   - Copy values from `backend/.env.example` into `backend/.env`
   - Set `GOOGLE_APPLICATION_CREDENTIALS` to your GCP service account JSON path
   - Set `DATABASE_URL` with your PostgreSQL credentials
   - Set `YOLO_MODEL_PATH` (default `yolov8n.pt`)
   - Optionally tune `QUEUE_MAX_SIZE`

4. Start API server:

   ```bash
   uvicorn app.main:app --reload
   ```

Backend runs on `http://127.0.0.1:8000`.

## PostgreSQL Setup

1. Ensure PostgreSQL is running locally or remotely.
2. Create database:

   ```sql
   CREATE DATABASE vehinsight;
   ```

3. Update `DATABASE_URL` in `backend/.env`:

   ```env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vehinsight
   ```

The app auto-creates tables on startup:

- `stream_jobs`
- `vehicle_analyses`

## Frontend Setup (Next.js)

1. Install dependencies:

   ```bash
   cd frontend
   npm install
   ```

2. Configure environment:

   - Copy `frontend/.env.local.example` to `frontend/.env.local`
   - Update `NEXT_PUBLIC_API_BASE_URL` if backend host differs

3. Run dev server:

   ```bash
   npm run dev
   ```

Frontend runs on `http://localhost:3000`.

## One-Command Start

From repository root:

```bat
start.bat
```

This starts backend and frontend in separate terminal windows.

## API Contract

### `POST /api/v1/stream-jobs/start`

Starts a new RTSP/video processing job.

Request:

```json
{
  "source_type": "rtsp",
  "source_uri": "rtsp://username:password@host:port/stream",
  "worker_count": 2,
  "sample_every_n_frames": 6,
  "confidence_threshold": 0.35,
  "max_frames": null
}
```

### `POST /api/v1/stream-jobs/{job_id}/stop`

Stops a running stream job.

### `GET /api/v1/stream-jobs/{job_id}`

Returns job status and counters:

- `processed_frames`
- `enqueued_tasks`
- `processed_tasks`

### `GET /api/v1/analyses?job_id=<id>&limit=<n>`

Returns persisted analysis summaries for a job.

### `GET /api/v1/analyses/recent?job_id=<id>&limit=<n>`

Returns detailed recent analysis records, including:

- bounding box
- colors
- annotated image (base64)

### `GET /health`

Returns service health:

```json
{ "status": "ok" }
```

## Notes

- Legacy standalone scripts were removed from the root to keep the repository clean.
- Stream processing logic lives in `backend/app/services/pipeline_service.py`.
- YOLO tracking is handled with the `ultralytics` package.
- For production deployment, use separate environment files per service and secure secret management.
