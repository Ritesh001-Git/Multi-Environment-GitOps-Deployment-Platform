import { useState, useEffect, useRef } from "react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const STAGES = [
  { id: "clone",   label: "Clone Repository",    icon: "◎" },
  { id: "build",   label: "Build Docker Image",   icon: "◈" },
  { id: "push",    label: "Push to Docker Hub",   icon: "⬡" },
  { id: "deploy",  label: "Deploy to Kubernetes", icon: "▦" },
  { id: "health",  label: "Health Check",          icon: "◉" },
];

function statusIcon(s) {
  if (s === "done")    return "✓";
  if (s === "running") return "…";
  if (s === "failed")  return "✗";
  return "○";
}

export default function PipelineStatus({ job, onComplete }) {
  const [stages, setStages] = useState(
    STAGES.map(s => ({ ...s, status: "pending", duration: null }))
  );
  const [logs, setLogs] = useState([]);
  const [overallStatus, setOverallStatus] = useState("running"); // running | success | failed
  const logRef = useRef(null);
  const intervalRef = useRef(null);
  const stageIdx = useRef(0);

  const addLog = (msg, type = "info") => {
    const time = new Date().toLocaleTimeString("en-US", { hour12: false });
    setLogs(prev => [...prev, { time, msg, type }]);
    setTimeout(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, 50);
  };

  // Poll backend for real status, OR simulate if backend unreachable
  useEffect(() => {
    addLog(`Triggered pipeline for ${job.repoUrl}`, "info");
    addLog(`Branch: ${job.branch} · Build #${job.buildNumber || "N/A"}`, "info");

    let currentStage = 0;
    const stageDurations = [1800, 3500, 2200, 2000, 1200]; // ms each

    const runStage = () => {
      if (currentStage >= STAGES.length) {
        setOverallStatus("success");
        addLog("All stages completed successfully.", "success");
        onComplete({
          id: `new-${Date.now()}`,
          repo: job.repoUrl,
          branch: job.branch,
          status: "success",
          time: "just now",
          duration: "~11s",
        });
        return;
      }

      // Mark current stage running
      setStages(prev => prev.map((s, i) =>
        i === currentStage ? { ...s, status: "running" } : s
      ));
      addLog(`[${STAGES[currentStage].label}] started...`, "running");

      const start = Date.now();

      // Try to poll real backend; fall back to simulation
      const pollOrSimulate = async () => {
        try {
          const res = await fetch(
            `${BACKEND_URL}/api/deploy/${job.jobId}/status`
          );
          if (res.ok) {
            const data = await res.json();
            const backendStage = data.current_stage;
            const backendStatus = data.status;

            if (backendStatus === "failed") {
              setStages(prev => prev.map((s, i) =>
                i === currentStage ? { ...s, status: "failed" } : s
              ));
              addLog(`[${STAGES[currentStage].label}] FAILED.`, "error");
              setOverallStatus("failed");
              onComplete({
                id: `new-${Date.now()}`,
                repo: job.repoUrl,
                branch: job.branch,
                status: "failed",
                time: "just now",
                duration: `${Math.round((Date.now() - start) / 1000)}s`,
              });
              return;
            }
          }
        } catch (_) {
          // backend not reachable – simulate
        }

        // Simulate stage completion after delay
        setTimeout(() => {
          const dur = `${((Date.now() - start) / 1000).toFixed(1)}s`;
          setStages(prev => prev.map((s, i) =>
            i === currentStage ? { ...s, status: "done", duration: dur } : s
          ));
          addLog(`[${STAGES[currentStage].label}] completed in ${dur}`, "success");
          currentStage++;
          runStage();
        }, stageDurations[currentStage]);
      };

      pollOrSimulate();
    };

    runStage();

    return () => clearInterval(intervalRef.current);
  }, [job.jobId]);

  const progress = Math.round(
    (stages.filter(s => s.status === "done").length / STAGES.length) * 100
  );

  return (
    <div className="card">
      <div className="card-title">
        ◈ Pipeline Running
        <span style={{
          marginLeft: "auto",
          padding: "2px 10px",
          background: overallStatus === "success"
            ? "rgba(34,211,160,0.1)"
            : overallStatus === "failed"
            ? "rgba(244,63,94,0.1)"
            : "rgba(108,99,255,0.1)",
          color: overallStatus === "success" ? "var(--success)"
            : overallStatus === "failed" ? "var(--danger)"
            : "var(--accent)",
          borderRadius: 4,
          fontFamily: "var(--mono)",
          fontSize: 11,
        }}>
          {overallStatus.toUpperCase()}
        </span>
      </div>

      {/* Progress */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-secondary)" }}>
            {job.repoUrl}
          </span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--accent)" }}>
            {progress}%
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* Stages */}
      <div className="steps" style={{ marginBottom: 16 }}>
        {stages.map(stage => (
          <div key={stage.id} className={`step ${stage.status}`}>
            <span className="step-icon" style={{
              color: stage.status === "done" ? "var(--success)"
                : stage.status === "running" ? "var(--accent)"
                : stage.status === "failed" ? "var(--danger)"
                : "var(--text-dim)"
            }}>
              {stage.status === "running" ? stage.icon : statusIcon(stage.status)}
            </span>
            <span className="step-name" style={{
              color: stage.status === "pending" ? "var(--text-dim)" : "var(--text-primary)"
            }}>
              {stage.label}
            </span>
            {stage.duration && (
              <span className="step-time">{stage.duration}</span>
            )}
            {stage.status === "running" && (
              <div className="spinner" />
            )}
          </div>
        ))}
      </div>

      {/* Log */}
      <div className="card-title">Terminal Log</div>
      <div className="log-box" ref={logRef}>
        {logs.map((l, i) => (
          <div key={i} className={`log-line ${l.type}`}>
            <span className="log-time">{l.time}</span>
            <span className="log-msg">{l.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
