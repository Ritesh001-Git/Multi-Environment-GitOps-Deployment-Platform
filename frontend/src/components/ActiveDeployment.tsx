// components/deployments/ActiveDeployment.tsx
// Real-time pipeline progress tracker — uses WebSocket with polling fallback

import React, { useEffect, useState } from "react";
import { useDeploymentSocket, useDeployment } from "../hooks";
import { StatusBadge, Spinner } from "./common/UI";
import { formatDuration } from "./common/utils";
import type { DeploymentStatusUpdate } from "../types";

const STAGES = [
  { id: "clone",  label: "Clone Repository",    icon: "⎇" },
  { id: "build",  label: "Build Docker Image",   icon: "◈" },
  { id: "push",   label: "Push to Docker Hub",   icon: "↑" },
  { id: "deploy", label: "Deploy to Kubernetes", icon: "☸" },
  { id: "health", label: "Health Check",          icon: "♡" },
];

// Infer which stage is active from elapsed time (rough heuristic until
// Jenkins stage data is available via API)
function inferStageIndex(status: string, durationSeconds: number | null): number {
  if (status !== "running") return -1;
  const s = durationSeconds ?? 0;
  if (s < 10)  return 0;
  if (s < 40)  return 1;
  if (s < 70)  return 2;
  if (s < 100) return 3;
  return 4;
}

interface Props {
  deploymentId: string;
  onComplete?: () => void;
}

export default function ActiveDeployment({ deploymentId, onComplete }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [startTime] = useState(Date.now());

  // WebSocket for real-time updates
  const { update: wsUpdate, connected } = useDeploymentSocket(deploymentId);

  // Polling fallback (also catches terminal state when WS closes)
  const { data: dep } = useDeployment(deploymentId, 5_000);

  // Use WS update if available, fall back to polled dep
  const status = wsUpdate?.status ?? dep?.status ?? "queued";
  const buildNumber = wsUpdate?.jenkins_build_number ?? dep?.jenkins_build_number;
  const buildUrl = wsUpdate?.jenkins_build_url ?? dep?.jenkins_build_url;
  const durationSeconds = wsUpdate?.duration_seconds ?? dep?.duration_seconds;

  const isTerminal =
    status === "success" || status === "failed" || status === "cancelled";
  const activeStage = inferStageIndex(status, elapsed / 1000);

  // Elapsed timer
  useEffect(() => {
    if (isTerminal) return;
    const t = setInterval(() => setElapsed(Date.now() - startTime), 1000);
    return () => clearInterval(t);
  }, [isTerminal, startTime]);

  useEffect(() => {
    if (isTerminal) onComplete?.();
  }, [isTerminal, onComplete]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="font-semibold text-gray-900">Pipeline Running</h3>
          <p className="text-xs text-gray-400 font-mono mt-0.5">
            {deploymentId.slice(0, 8)}
            {buildNumber && ` · Build #${buildNumber}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            {connected ? "🟢 live" : "⚪ polling"}
          </span>
          <StatusBadge status={status as any} />
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-5">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Progress</span>
          <span>
            {isTerminal
              ? formatDuration(durationSeconds)
              : `${Math.round(elapsed / 1000)}s`}
          </span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              status === "success"
                ? "bg-emerald-500 w-full"
                : status === "failed"
                ? "bg-red-500"
                : "bg-indigo-500"
            }`}
            style={{
              width:
                status === "success"
                  ? "100%"
                  : status === "failed"
                  ? `${Math.min(((activeStage + 1) / STAGES.length) * 100, 95)}%`
                  : `${Math.max(4, ((activeStage + 0.5) / STAGES.length) * 100)}%`,
            }}
          />
        </div>
      </div>

      {/* Stage list */}
      <div className="space-y-2">
        {STAGES.map((stage, idx) => {
          const isDone = isTerminal
            ? status === "success"
            : idx < activeStage;
          const isActive = !isTerminal && idx === activeStage;
          const isFailed = status === "failed" && idx === activeStage;

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                isDone
                  ? "bg-emerald-50 border border-emerald-100"
                  : isActive
                  ? "bg-indigo-50 border border-indigo-200"
                  : isFailed
                  ? "bg-red-50 border border-red-200"
                  : "border border-transparent"
              }`}
            >
              {/* Stage icon */}
              <span
                className={`w-6 h-6 flex items-center justify-center rounded-full text-sm flex-shrink-0 ${
                  isDone
                    ? "bg-emerald-500 text-white"
                    : isActive
                    ? "bg-indigo-500 text-white"
                    : isFailed
                    ? "bg-red-500 text-white"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {isDone ? "✓" : isFailed ? "✗" : stage.icon}
              </span>

              {/* Stage name */}
              <span
                className={`text-sm font-medium flex-1 ${
                  isDone
                    ? "text-emerald-700"
                    : isActive
                    ? "text-indigo-700"
                    : isFailed
                    ? "text-red-700"
                    : "text-gray-400"
                }`}
              >
                {stage.label}
              </span>

              {/* Right side */}
              {isActive && !isFailed && <Spinner size="sm" />}
            </div>
          );
        })}
      </div>

      {/* Footer links */}
      {buildUrl && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <a
            href={buildUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-600 hover:underline"
          >
            View full Jenkins log ↗
          </a>
        </div>
      )}
    </div>
  );
}