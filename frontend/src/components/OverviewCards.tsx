// components/dashboard/OverviewCards.tsx
// Replaces all hardcoded stat values with live data from useDashboardStats()

import React from "react";
import { useDashboardStats } from "../hooks";
import { StatCard, ErrorBanner, LiveIndicator } from "./common/UI";
import { formatDuration } from "./common/utils";

export default function OverviewCards() {
  const { data, loading, error, refresh } = useDashboardStats(10_000);

  if (error) {
    return <ErrorBanner message={`Stats unavailable: ${error}`} onRetry={refresh} />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">Overview</h2>
        <LiveIndicator active={!loading} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Deployments"
          value={data?.total_deployments ?? "—"}
          sub="all time"
          accent="text-indigo-600"
          loading={loading && !data}
        />

        <StatCard
          label="Success Rate"
          value={data ? `${data.success_rate}%` : "—"}
          sub={
            data
              ? `${data.successful_deployments} succeeded · ${data.failed_deployments} failed`
              : undefined
          }
          accent={
            (data?.success_rate ?? 0) >= 80
              ? "text-emerald-600"
              : "text-red-600"
          }
          loading={loading && !data}
        />

        <StatCard
          label="Running Pods"
          value={data?.running_pods ?? "—"}
          sub={
            data?.running_deployments
              ? `${data.running_deployments} deploy in progress`
              : "cluster healthy"
          }
          accent="text-blue-600"
          loading={loading && !data}
        />

        <StatCard
          label="Active Services"
          value={data?.active_services ?? "—"}
          sub={
            data?.avg_duration_seconds != null
              ? `avg build ${formatDuration(data.avg_duration_seconds)}`
              : "kubernetes services"
          }
          accent="text-gray-900"
          loading={loading && !data}
        />
      </div>

      {/* Secondary row */}
      <div className="grid grid-cols-3 gap-4 mt-4">
        <StatCard
          label="Succeeded"
          value={data?.successful_deployments ?? "—"}
          accent="text-emerald-600"
          loading={loading && !data}
        />
        <StatCard
          label="Failed"
          value={data?.failed_deployments ?? "—"}
          accent="text-red-600"
          loading={loading && !data}
        />
        <StatCard
          label="Avg Build Time"
          value={formatDuration(data?.avg_duration_seconds ?? null)}
          accent="text-gray-700"
          loading={loading && !data}
        />
      </div>
    </div>
  );
}