// components/deployments/DeploymentTable.tsx
// Full dynamic deployment history — replaces all static placeholder rows

import React, { useState } from "react";
import { useDeployments } from "../hooks";
import {
  StatusBadge,
  ErrorBanner,
  EmptyState,
  Skeleton,
  SectionHeader,
  LiveIndicator,
} from "./common/UI";
import {
  formatDuration,
  formatRelativeTime,
  formatDateTime,
  truncate,
} from "./common/utils";
import type { Deployment, DeploymentStatus } from "../types";

const STATUS_FILTERS: { label: string; value: DeploymentStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Running", value: "running" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
  { label: "Queued", value: "queued" },
];

const PAGE_SIZE = 20;

export default function DeploymentTable() {
  const [statusFilter, setStatusFilter] = useState<DeploymentStatus | "">("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Deployment | null>(null);

  const { data, loading, error, refresh } = useDeployments(
    {
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      status: statusFilter || undefined,
    },
    8_000
  );

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div>
      <SectionHeader
        title="Deployment History"
        subtitle={data ? `${data.total} total deployments` : undefined}
        action={<LiveIndicator />}
      />

      {/* Status filter tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => {
              setStatusFilter(f.value as DeploymentStatus | "");
              setPage(0);
            }}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              statusFilter === f.value
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <ErrorBanner
          message={`Could not load deployments: ${error}`}
          onRetry={refresh}
        />
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Repository
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Branch
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Build #
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Duration
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Triggered
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Environment
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading && !data
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                : data?.items.map((dep) => (
                    <DeploymentRow
                      key={dep.id}
                      dep={dep}
                      onClick={() =>
                        setSelected(selected?.id === dep.id ? null : dep)
                      }
                      isSelected={selected?.id === dep.id}
                    />
                  ))}
            </tbody>
          </table>
        </div>

        {data?.items.length === 0 && !loading && (
          <EmptyState
            icon="🚀"
            title="No deployments yet"
            subtitle="Submit a GitHub repository URL to trigger your first build."
          />
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              Page {page + 1} of {totalPages} · {data?.total} total
            </p>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                ← Prev
              </button>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selected && <DeploymentDetail dep={selected} />}
    </div>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

function DeploymentRow({
  dep,
  onClick,
  isSelected,
}: {
  dep: Deployment;
  onClick: () => void;
  isSelected: boolean;
}) {
  return (
    <tr
      onClick={onClick}
      className={`cursor-pointer transition-colors hover:bg-gray-50 ${
        isSelected ? "bg-indigo-50" : ""
      }`}
    >
      <td className="px-4 py-3">
        <div className="font-medium text-gray-900">{dep.repo_name}</div>
        {dep.docker_image && (
          <div className="text-xs text-gray-400 font-mono mt-0.5">
            {truncate(dep.docker_image, 40)}
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
          {dep.branch}
        </span>
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={dep.status} />
      </td>
      <td className="px-4 py-3">
        {dep.jenkins_build_number ? (
          dep.jenkins_build_url ? (
            <a
              href={dep.jenkins_build_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-indigo-600 hover:underline font-mono text-xs"
            >
              #{dep.jenkins_build_number}
            </a>
          ) : (
            <span className="font-mono text-xs text-gray-500">
              #{dep.jenkins_build_number}
            </span>
          )
        ) : (
          <span className="text-gray-300 text-xs">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-gray-600 tabular-nums text-xs">
        {formatDuration(dep.duration_seconds)}
      </td>
      <td className="px-4 py-3 text-gray-500 text-xs">
        <span title={formatDateTime(dep.started_at)}>
          {formatRelativeTime(dep.started_at)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-xs text-gray-500 capitalize">
          {dep.environment.replace("-", " ")}
        </span>
      </td>
    </tr>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function DeploymentDetail({ dep }: { dep: Deployment }) {
  return (
    <div className="mt-4 bg-white rounded-xl border border-indigo-200 p-5">
      <h3 className="font-semibold text-gray-900 mb-4">
        Deployment Detail — {dep.id.slice(0, 8)}
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-y-4 gap-x-8 text-sm">
        <Field label="Repository" value={dep.repo_url} mono link={dep.repo_url} />
        <Field label="Branch" value={dep.branch} mono />
        <Field label="Status" value={<StatusBadge status={dep.status} />} />
        <Field label="Docker Image" value={dep.docker_image ?? "—"} mono />
        <Field label="Image Tag" value={dep.docker_tag ?? "—"} mono />
        <Field label="Namespace" value={dep.k8s_namespace} mono />
        <Field label="Started" value={formatDateTime(dep.started_at)} />
        <Field label="Finished" value={formatDateTime(dep.finished_at)} />
        <Field label="Duration" value={formatDuration(dep.duration_seconds)} />
        <Field label="Triggered by" value={dep.triggered_by} />
        <Field label="Environment" value={dep.environment} />
        {dep.commit_sha && (
          <Field label="Commit" value={dep.commit_sha.slice(0, 7)} mono />
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
  link,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  link?: string;
}) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      {link ? (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className={`text-indigo-600 hover:underline break-all ${mono ? "font-mono text-xs" : ""}`}
        >
          {value}
        </a>
      ) : (
        <p
          className={`text-gray-900 break-all ${mono ? "font-mono text-xs" : "font-medium"}`}
        >
          {value}
        </p>
      )}
    </div>
  );
}