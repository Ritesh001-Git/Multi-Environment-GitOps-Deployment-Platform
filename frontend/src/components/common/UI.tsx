// components/common/UI.tsx — Reusable building blocks

import React from "react";
import type { DeploymentStatus } from "../../types";
import { STATUS_CONFIG, POD_STATUS_CONFIG } from "./utils";

// ── Loading skeleton ──────────────────────────────────────────────────────────

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

// ── Error banner ──────────────────────────────────────────────────────────────

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      <span className="mt-0.5">⚠</span>
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="ml-2 underline hover:no-underline text-red-600 whitespace-nowrap"
        >
          Retry
        </button>
      )}
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: DeploymentStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.failed;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${cfg.badge} ${cfg.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ── Pod status badge ──────────────────────────────────────────────────────────

export function PodStatusBadge({ status }: { status: string }) {
  const cfg = POD_STATUS_CONFIG[status] ?? POD_STATUS_CONFIG["Unknown"];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${cfg.badge} ${cfg.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {status}
    </span>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

export function EmptyState({
  icon = "📭",
  title,
  subtitle,
}: {
  icon?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-5xl mb-4">{icon}</div>
      <p className="text-gray-700 font-semibold">{title}</p>
      {subtitle && <p className="text-gray-400 text-sm mt-1">{subtitle}</p>}
    </div>
  );
}

// ── Stats card ────────────────────────────────────────────────────────────────

export function StatCard({
  label,
  value,
  sub,
  accent = "text-gray-900",
  loading = false,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
  loading?: boolean;
}) {
  if (loading) return <CardSkeleton />;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 hover:border-gray-300 transition-colors">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        {label}
      </p>
      <p className={`text-3xl font-bold leading-none ${accent}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-2">{sub}</p>}
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────────

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sz = { sm: "w-4 h-4", md: "w-6 h-6", lg: "w-10 h-10" }[size];
  return (
    <div
      className={`${sz} border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin`}
    />
  );
}

// ── Section header ────────────────────────────────────────────────────────────

export function SectionHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">{title}</h2>
        {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

// ── Live indicator ────────────────────────────────────────────────────────────

export function LiveIndicator({ active = true }: { active?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
      <span
        className={`w-2 h-2 rounded-full ${
          active ? "bg-emerald-500 animate-pulse" : "bg-gray-300"
        }`}
      />
      {active ? "Live" : "Paused"}
    </span>
  );
}