// pages/Dashboard.tsx
// Wires all components together — drop this into your existing page layout

import React, { useState } from "react";
import OverviewCards from "../components/OverviewCards";
import DeployForm from "../components/DeployForm";
import DeploymentTable from "../components/DeploymentTable";
import ActiveDeployment from "../components/ActiveDeployment";
import PodMonitor from "../components/PodMonitor";

type Tab = "overview" | "deployments" | "pods";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [activeDeploymentId, setActiveDeploymentId] = useState<string | null>(null);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "overview",    label: "Overview",    icon: "⬡" },
    { id: "deployments", label: "Deployments", icon: "◈" },
    { id: "pods",        label: "Pods",        icon: "☸" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-14">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-white text-sm">
              ⬡
            </div>
            <span className="font-bold text-gray-900">GitOps Platform</span>
          </div>

          {/* Tab navigation */}
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === t.id
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                }`}
              >
                <span>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* ── Overview tab ─────────────────────────────────────────────── */}
        {activeTab === "overview" && (
          <>
            <OverviewCards />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Deploy form */}
              <div className="lg:col-span-1 space-y-4">
                <DeployForm
                  onDeploymentStarted={(id) => {
                    setActiveDeploymentId(id);
                    setActiveTab("deployments");
                  }}
                />

                {/* Quick links */}
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                    Tools
                  </p>
                  <div className="space-y-2">
                    {[
                      {
                        label: "Jenkins",
                        url: `${import.meta.env.VITE_JENKINS_URL ?? "http://localhost:8080"}`,
                        icon: "◉",
                      },
                      { label: "Grafana", url: `${import.meta.env.VITE_GRAFANA_URL ?? "http://localhost:3001"}`, icon: "📊" },
                      { label: "Prometheus", url: `${import.meta.env.VITE_PROMETHEUS_URL ?? "http://localhost:9090"}`, icon: "📈" },
                      {
                        label: "API Docs",
                        url: `${import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000"}/docs`,
                        icon: "📖",
                      },
                    ].map((link) => (
                      <a
                        key={link.label}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors group"
                      >
                        <span className="flex items-center gap-2 text-sm text-gray-600">
                          <span>{link.icon}</span>
                          {link.label}
                        </span>
                        <span className="text-gray-300 group-hover:text-gray-500 text-xs">
                          ↗
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              </div>

              {/* Recent deployments preview */}
              <div className="lg:col-span-2">
                <DeploymentTable />
              </div>
            </div>
          </>
        )}

        {/* ── Deployments tab ──────────────────────────────────────────── */}
        {activeTab === "deployments" && (
          <div className="space-y-6">
            {/* Active pipeline tracker */}
            {activeDeploymentId && (
              <ActiveDeployment
                deploymentId={activeDeploymentId}
                onComplete={() => {
                  // Keep showing it but allow dismissal
                }}
              />
            )}

            {activeDeploymentId && (
              <div className="flex justify-end">
                <button
                  onClick={() => setActiveDeploymentId(null)}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Dismiss tracker
                </button>
              </div>
            )}

            <DeploymentTable />
          </div>
        )}

        {/* ── Pods tab ─────────────────────────────────────────────────── */}
        {activeTab === "pods" && <PodMonitor />}
      </main>
    </div>
  );
}