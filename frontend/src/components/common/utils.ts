// components/common/utils.ts — formatting helpers + shared UI atoms

import type { DeploymentStatus } from "../../types";

// ── Status badge config ───────────────────────────────────────────────────────

export const STATUS_CONFIG: Record<
  DeploymentStatus,
  { label: string; dot: string; badge: string; text: string }
> = {
  queued: {
    label: "Queued",
    dot: "bg-amber-400",
    badge: "bg-amber-50 border border-amber-200",
    text: "text-amber-700",
  },
  running: {
    label: "Running",
    dot: "bg-blue-500 animate-pulse",
    badge: "bg-blue-50 border border-blue-200",
    text: "text-blue-700",
  },
  success: {
    label: "Success",
    dot: "bg-emerald-500",
    badge: "bg-emerald-50 border border-emerald-200",
    text: "text-emerald-700",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-500",
    badge: "bg-red-50 border border-red-200",
    text: "text-red-700",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-gray-400",
    badge: "bg-gray-50 border border-gray-200",
    text: "text-gray-500",
  },
};

export const POD_STATUS_CONFIG: Record<
  string,
  { badge: string; text: string; dot: string }
> = {
  Running: {
    badge: "bg-emerald-50 border border-emerald-200",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
  Pending: {
    badge: "bg-amber-50 border border-amber-200",
    text: "text-amber-700",
    dot: "bg-amber-400 animate-pulse",
  },
  Failed: {
    badge: "bg-red-50 border border-red-200",
    text: "text-red-700",
    dot: "bg-red-500",
  },
  Succeeded: {
    badge: "bg-gray-50 border border-gray-200",
    text: "text-gray-500",
    dot: "bg-gray-400",
  },
  Unknown: {
    badge: "bg-gray-50 border border-gray-200",
    text: "text-gray-400",
    dot: "bg-gray-300",
  },
};

// ── Formatters ────────────────────────────────────────────────────────────────

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export function formatAge(ageSeconds: number): string {
  if (ageSeconds < 60) return `${ageSeconds}s`;
  if (ageSeconds < 3600) return `${Math.floor(ageSeconds / 60)}m`;
  if (ageSeconds < 86400) return `${Math.floor(ageSeconds / 3600)}h`;
  return `${Math.floor(ageSeconds / 86400)}d`;
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + "…" : str;
}

export function repoName(repoUrl: string): string {
  const parts = repoUrl.replace("https://github.com/", "").split("/");
  return parts.slice(0, 2).join("/");
}