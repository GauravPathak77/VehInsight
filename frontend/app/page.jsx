"use client";

import { useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function HomePage() {
  const [sourceType, setSourceType] = useState("rtsp");
  const [sourceUri, setSourceUri] = useState("");
  const [sampleEveryNFrames, setSampleEveryNFrames] = useState(6);
  const [workerCount, setWorkerCount] = useState(2);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.35);
  const [maxFrames, setMaxFrames] = useState("");
  const [job, setJob] = useState(null);
  const [recentResults, setRecentResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!job?.id) {
      return;
    }
    const intervalId = setInterval(async () => {
      try {
        const [jobResponse, resultResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/stream-jobs/${job.id}`),
          fetch(`${API_BASE_URL}/api/v1/analyses/recent?job_id=${job.id}&limit=12`),
        ]);

        if (jobResponse.ok) {
          setJob(await jobResponse.json());
        }
        if (resultResponse.ok) {
          setRecentResults(await resultResponse.json());
        }
      } catch {
        // Polling is best-effort.
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [job?.id]);

  const handleStart = async (event) => {
    event.preventDefault();
    if (!sourceUri.trim()) {
      setError("Please provide RTSP URL or video file path.");
      return;
    }

    setLoading(true);
    setError("");
    setRecentResults([]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/stream-jobs/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: sourceType,
          source_uri: sourceUri.trim(),
          worker_count: Number(workerCount),
          sample_every_n_frames: Number(sampleEveryNFrames),
          confidence_threshold: Number(confidenceThreshold),
          max_frames: maxFrames ? Number(maxFrames) : null,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail ?? "Failed to start stream job.");
      }

      setJob(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!job?.id) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/stream-jobs/${job.id}/stop`, {
        method: "POST",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail ?? "Failed to stop stream job.");
      }
      setJob(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      <h1>VehInsight Stream Analyzer</h1>
      <p className="subtitle">
        Analyze RTSP/video feeds with YOLO tracking and queue-based workers.
      </p>

      <form className="panel" onSubmit={handleStart}>
        <label>
          Source Type
          <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
            <option value="rtsp">RTSP</option>
            <option value="video_file">Video File</option>
          </select>
        </label>
        <label>
          Source URI / File Path
          <input
            type="text"
            value={sourceUri}
            onChange={(event) => setSourceUri(event.target.value)}
            placeholder={
              sourceType === "rtsp"
                ? "rtsp://username:password@host:port/stream"
                : "C:/videos/input.mp4"
            }
          />
        </label>
        <label>
          Sample Every N Frames
          <input
            type="number"
            min={1}
            value={sampleEveryNFrames}
            onChange={(event) => setSampleEveryNFrames(event.target.value)}
          />
        </label>
        <label>
          Worker Count
          <input
            type="number"
            min={1}
            max={8}
            value={workerCount}
            onChange={(event) => setWorkerCount(event.target.value)}
          />
        </label>
        <label>
          Confidence Threshold
          <input
            type="number"
            step="0.05"
            min="0.1"
            max="0.95"
            value={confidenceThreshold}
            onChange={(event) => setConfidenceThreshold(event.target.value)}
          />
        </label>
        <label>
          Max Frames (optional)
          <input
            type="number"
            min={1}
            value={maxFrames}
            onChange={(event) => setMaxFrames(event.target.value)}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Starting..." : "Start Stream Job"}
        </button>
        <button
          type="button"
          onClick={handleStop}
          disabled={loading || !job || ["completed", "failed", "stopped"].includes(job.status)}
          style={{ marginLeft: "0.5rem", backgroundColor: "#b91c1c" }}
        >
          Stop Job
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {job && (
        <section className="panel">
          <h2>Job Status</h2>
          <p>
            <strong>Job ID:</strong> {job.id}
          </p>
          <p>
            <strong>Status:</strong> {job.status}
          </p>
          <p>
            <strong>Processed Frames:</strong> {job.processed_frames}
          </p>
          <p>
            <strong>Enqueued Tasks:</strong> {job.enqueued_tasks}
          </p>
          <p>
            <strong>Processed Tasks:</strong> {job.processed_tasks}
          </p>
          {job.error_message && (
            <p className="error">
              <strong>Error:</strong> {job.error_message}
            </p>
          )}
        </section>
      )}

      {recentResults.length > 0 && (
        <section className="panel">
          <h2>Recent Analyses</h2>
          {recentResults.map((item) => (
            <article key={item.id} className="panel" style={{ marginTop: "0.75rem" }}>
              <p>
                <strong>Frame:</strong> {item.frame_index} | <strong>Track:</strong>{" "}
                {item.track_id ?? "N/A"}
              </p>
              <p>
                <strong>Logo:</strong> {item.logo}
              </p>
              <p>
                <strong>Plate:</strong> {item.plate_number}
              </p>
              <div className="colors">
                {item.colors.map((color) => (
                  <div key={`${item.id}-${color.name}-${color.rgb.join("-")}`} className="colorRow">
                    <div
                      className="swatch"
                      style={{ backgroundColor: `rgb(${color.rgb.join(",")})` }}
                    />
                    <span>
                      {color.name} - {Math.round(color.confidence * 100)}%
                    </span>
                  </div>
                ))}
              </div>
              <img
                src={`data:image/png;base64,${item.annotated_image_base64}`}
                alt={`Analysis ${item.id}`}
                className="preview"
              />
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
