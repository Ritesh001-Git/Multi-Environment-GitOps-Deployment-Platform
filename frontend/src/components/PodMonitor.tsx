// components/pods/PodMonitor.tsx
// Real Kubernetes pod data from the backend — replaces all static pod cards

import React, { useState } from "react";
import { useK8sOverview } from "../hooks";
import {
  PodStatusBadge,
  ErrorBanner,
  EmptyState,
  SectionHeader,
  LiveIndicator,
  Skeleton,
  StatCard,
} from "./common/UI";
import { formatAge } from "./common/utils";
import type { Pod } from "../types";

const NAMESPACE_OPTIONS = ["default", "kube-system", "all"];

export default function PodMonitor() {
  const [namespace, setNamespace] = useState("default");
  const [view, setView] = useState<"cards" | "table">("cards");

  const { data, loading, error, refresh } = useK8sOverview(namespace, 15_000);

  return (
    <div>
      <SectionHeader
        title="Pod Monitoring"
        subtitle="Live Kubernetes cluster state"
        action={<LiveIndicator />}
      />

      {/* Controls */}
      <div className="flex flex-wrap gap-3 mb-6">
        {/* Namespace selector */}
        <select
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
        >
          {NAMESPACE_OPTIONS.map((ns) => (
            <option key={ns} value={ns}>
              {ns === "all" ? "All Namespaces" : `ns: ${ns}`}
            </option>
          ))}
        </select>

        {/* View toggle */}
        <div className="flex bg-gray-100 rounded-lg p-1">
          {(["cards", "table"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all capitalize ${
                view === v
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        <button
          onClick={refresh}
          className="ml-auto text-xs text-indigo-600 hover:underline"
        >
          ↻ Refresh
        </button>
      </div>

      {error && (
        <ErrorBanner
          message={`Kubernetes not reachable: ${error}. Is Minikube running?`}
          onRetry={refresh}
        />
      )}

      {/* Cluster summary bar */}
      {(data || loading) && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          <StatCard
            label="Total Pods"
            value={data?.total_pods ?? "—"}
            loading={loading && !data}
          />
          <StatCard
            label="Running"
            value={data?.running_pods ?? "—"}
            accent="text-emerald-600"
            loading={loading && !data}
          />
          <StatCard
            label="Pending"
            value={data?.pending_pods ?? "—"}
            accent="text-amber-600"
            loading={loading && !data}
          />
          <StatCard
            label="Failed"
            value={data?.failed_pods ?? "—"}
            accent="text-red-600"
            loading={loading && !data}
          />
        </div>
      )}

      {/* Pod list */}
      {loading && !data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
              <Skeleton className="h-4 w-3/4 mb-3" />
              <Skeleton className="h-3 w-1/2 mb-2" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          ))}
        </div>
      ) : data?.pods.length === 0 ? (
        <EmptyState
          icon="☸"
          title="No pods found"
          subtitle={`No pods in namespace '${namespace}'. Is Minikube running?`}
        />
      ) : view === "cards" ? (
        <PodCardGrid pods={data?.pods ?? []} />
      ) : (
        <PodTable pods={data?.pods ?? []} />
      )}

      {/* K8s Deployments section */}
      {data && data.deployments.length > 0 && (
        <div className="mt-8">
          <h3 className="text-base font-semibold text-gray-900 mb-4">
            Kubernetes Deployments
          </h3>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Name", "Namespace", "Ready", "Available", "Image"].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.deployments.map((dep) => (
                  <tr key={dep.name} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900 font-mono text-xs">
                      {dep.name}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {dep.namespace}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-semibold ${
                          dep.ready_replicas === dep.desired_replicas
                            ? "text-emerald-600"
                            : "text-amber-600"
                        }`}
                      >
                        {dep.ready_replicas}/{dep.desired_replicas}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      {dep.available_replicas}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500 max-w-xs truncate">
                      {dep.image}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Card grid view ────────────────────────────────────────────────────────────

function PodCardGrid({ pods }: { pods: Pod[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {pods.map((pod) => (
        <PodCard key={`${pod.namespace}/${pod.name}`} pod={pod} />
      ))}
    </div>
  );
}

function PodCard({ pod }: { pod: Pod }) {
  return (
    <div
      className={`bg-white rounded-xl border p-4 transition-all hover:shadow-sm ${
        pod.status === "Running"
          ? "border-gray-200"
          : pod.status === "Pending"
          ? "border-amber-200"
          : "border-red-200"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="font-mono text-xs font-semibold text-gray-900 truncate">
            {pod.name}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{pod.namespace}</p>
        </div>
        <PodStatusBadge status={pod.status} />
      </div>

      {/* Meta grid */}
      <div className="grid grid-cols-2 gap-y-2 text-xs">
        <PodMeta label="Image" value={pod.image} mono truncatable />
        <PodMeta label="Tag" value={pod.image_tag} mono />
        <PodMeta label="Node" value={pod.node_name ?? "—"} mono truncatable />
        <PodMeta label="Age" value={formatAge(pod.age_seconds)} />
        <PodMeta
          label="Restarts"
          value={String(pod.restart_count)}
          accent={pod.restart_count > 3 ? "text-red-600 font-bold" : undefined}
        />
        <PodMeta label="Ready" value={pod.ready ? "✓ Yes" : "✗ No"} accent={pod.ready ? "text-emerald-600" : "text-red-600"} />
      </div>
    </div>
  );
}

function PodMeta({
  label,
  value,
  mono = false,
  truncatable = false,
  accent,
}: {
  label: string;
  value: string;
  mono?: boolean;
  truncatable?: boolean;
  accent?: string;
}) {
  return (
    <div className={truncatable ? "min-w-0" : ""}>
      <p className="text-gray-400">{label}</p>
      <p
        className={`${mono ? "font-mono" : "font-medium"} text-gray-700 ${accent ?? ""} ${truncatable ? "truncate" : ""}`}
      >
        {value}
      </p>
    </div>
  );
}

// ── Table view ────────────────────────────────────────────────────────────────

function PodTable({ pods }: { pods: Pod[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Pod Name", "Namespace", "Status", "Image", "Tag", "Node", "Restarts", "Age"].map(
                (h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap"
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {pods.map((pod) => (
              <tr key={`${pod.namespace}/${pod.name}`} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-gray-900 max-w-xs truncate">
                  {pod.name}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{pod.namespace}</td>
                <td className="px-4 py-3">
                  <PodStatusBadge status={pod.status} />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600 max-w-xs truncate">
                  {pod.image}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{pod.image_tag}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500 max-w-xs truncate">
                  {pod.node_name ?? "—"}
                </td>
                <td className={`px-4 py-3 text-xs font-semibold ${pod.restart_count > 3 ? "text-red-600" : "text-gray-700"}`}>
                  {pod.restart_count}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {formatAge(pod.age_seconds)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}