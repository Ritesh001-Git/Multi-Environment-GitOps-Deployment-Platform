import { useState, useEffect, useRef } from "react";
import DeployForm from "../components/DeployForm";
import PipelineStatus from "../components/PipelineStatus";
import DeploymentHistory from "../components/DeploymentHistory";

const NAV = [
  { icon: "⬡", label: "Overview",   id: "overview" },
  { icon: "⚡", label: "Deploy",     id: "deploy" },
  { icon: "◈",  label: "Pipelines",  id: "pipelines" },
  { icon: "▦",  label: "Pods",       id: "pods" },
  { icon: "◉",  label: "Monitoring", id: "monitoring" },
];

const INITIAL_STATS = {
  deployments: 12,
  running: 3,
  success: 91,
  uptime: "99.8%",
};

export default function Dashboard() {
  const [activeNav, setActiveNav] = useState("deploy");
  const [activeDeploy, setActiveDeploy] = useState(null); // current pipeline run
  const [history, setHistory] = useState([
    { id: "d-001", repo: "github.com/user/api-service",  branch: "main",    status: "success", time: "2m ago",  duration: "1m 24s" },
    { id: "d-002", repo: "github.com/user/web-frontend", branch: "develop", status: "success", time: "18m ago", duration: "2m 03s" },
    { id: "d-003", repo: "github.com/user/auth-service",  branch: "fix/jwt", status: "failed",  time: "1h ago",  duration: "0m 47s" },
    { id: "d-004", repo: "github.com/user/data-worker",  branch: "main",    status: "success", time: "3h ago",  duration: "1m 55s" },
  ]);

  const addToHistory = (entry) => {
    setHistory(prev => [entry, ...prev.slice(0, 9)]);
  };

  const stats = {
    ...INITIAL_STATS,
    deployments: INITIAL_STATS.deployments + history.filter(h => h.id.startsWith("new")).length,
    running: activeDeploy ? INITIAL_STATS.running + 1 : INITIAL_STATS.running,
  };

  return (
    <div className="shell">
      {/* Topbar */}
      <header className="topbar">
        <div className="logo">
          <div className="logo-icon">⬡</div>
          GitOps Platform
        </div>
        <div className="topbar-right">
          <div className="status-dot" />
          <span>cluster: minikube</span>
          <span style={{ color: "var(--border-active)" }}>|</span>
          <span>namespace: default</span>
          <span style={{ color: "var(--border-active)" }}>|</span>
          <span style={{ color: "var(--success)" }}>3 pods running</span>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="nav-section">Navigation</div>
        {NAV.map(n => (
          <div
            key={n.id}
            className={`nav-item ${activeNav === n.id ? "active" : ""}`}
            onClick={() => setActiveNav(n.id)}
          >
            <span className="nav-icon">{n.icon}</span>
            {n.label}
          </div>
        ))}

        <div className="nav-section" style={{ marginTop: 24 }}>Cluster</div>
        <div className="nav-item">
          <span className="nav-icon">◎</span> Minikube
        </div>
        <div className="nav-item">
          <span className="nav-icon">◫</span> Docker Hub
        </div>
        <div className="nav-item">
          <span className="nav-icon">⊟</span> Jenkins
        </div>

        <div style={{ marginTop: "auto", padding: "12px", borderTop: "1px solid var(--border)" }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-dim)" }}>
            v1.0.0-mvp · Local K8s
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main">
        <div className="page-header">
          <div>
            <div className="page-title">
              {activeNav === "deploy" && "New Deployment"}
              {activeNav === "overview" && "Overview"}
              {activeNav === "pipelines" && "Pipeline History"}
              {activeNav === "pods" && "Pod Status"}
              {activeNav === "monitoring" && "Monitoring"}
            </div>
            <div className="page-sub">
              {new Date().toLocaleString("en-US", {
                weekday: "short", month: "short", day: "numeric",
                hour: "2-digit", minute: "2-digit",
              })}
            </div>
          </div>
        </div>

        {/* Stat row - always visible */}
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Total Deploys</div>
            <div className="stat-value purple">{stats.deployments}</div>
            <div className="stat-meta">all time</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Running Pods</div>
            <div className="stat-value green">{stats.running}</div>
            <div className="stat-meta">across namespace</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Success Rate</div>
            <div className="stat-value green">{stats.success}%</div>
            <div className="stat-meta">last 30 days</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Uptime</div>
            <div className="stat-value">{stats.uptime}</div>
            <div className="stat-meta">30-day average</div>
          </div>
        </div>

        {/* Deploy tab */}
        {activeNav === "deploy" && (
          <div className="three-col">
            <DeployForm
              onDeploy={(job) => {
                setActiveDeploy(job);
                setActiveNav("pipelines");
              }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="card">
                <div className="card-title">⚡ Quick Tips</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.9, fontFamily: "var(--mono)" }}>
                  <div>→ Use HTTPS clone URL</div>
                  <div>→ Branch defaults to <span style={{color:"var(--accent)"}}>main</span></div>
                  <div>→ Dockerfile must be at root</div>
                  <div>→ k8s/ folder auto-applied</div>
                  <div>→ Webhook triggers auto-deploy</div>
                </div>
              </div>
              <div className="card">
                <div className="card-title">◉ Jenkins</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-secondary)" }}>
                    localhost:8080
                  </div>
                  <a
                    href="http://localhost:8080"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-ghost"
                    style={{ padding: "6px 12px", fontSize: 11, textDecoration: "none" }}
                  >
                    Open ↗
                  </a>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Overview tab */}
        {activeNav === "overview" && (
          <DeploymentHistory history={history} />
        )}

        {/* Pipelines tab */}
        {activeNav === "pipelines" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {activeDeploy && (
              <PipelineStatus
                job={activeDeploy}
                onComplete={(entry) => {
                  addToHistory(entry);
                  setActiveDeploy(null);
                }}
              />
            )}
            <DeploymentHistory history={history} />
          </div>
        )}

        {/* Pods tab */}
        {activeNav === "pods" && (
          <div className="card">
            <div className="card-title">▦ Kubernetes Pods</div>
            <table className="table">
              <thead>
                <tr>
                  <th>Pod Name</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>Restarts</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: "api-service-7d9f-xk2p",  image: "myapp/api:latest",     status: "Running",  restarts: 0, age: "2d" },
                  { name: "web-frontend-5c8b-m3np",  image: "myapp/frontend:v1.2",  status: "Running",  restarts: 1, age: "2d" },
                  { name: "auth-service-9a1c-zq4w",  image: "myapp/auth:stable",    status: "Running",  restarts: 0, age: "5d" },
                  { name: "data-worker-2b3d-lp9x",   image: "myapp/worker:latest",  status: "Pending",  restarts: 3, age: "1h" },
                ].map(pod => (
                  <tr key={pod.name}>
                    <td style={{ color: "var(--text-primary)" }}>{pod.name}</td>
                    <td>{pod.image}</td>
                    <td>
                      <span className={`badge ${pod.status === "Running" ? "badge-success" : "badge-pending"}`}>
                        {pod.status === "Running" ? "●" : "○"} {pod.status}
                      </span>
                    </td>
                    <td>{pod.restarts}</td>
                    <td>{pod.age}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Monitoring tab */}
        {activeNav === "monitoring" && (
          <div className="two-col">
            <div className="card">
              <div className="card-title">◉ Grafana Dashboard</div>
              <div style={{ padding: "20px 0", textAlign: "center" }}>
                <div style={{ fontSize: 40, marginBottom: 10 }}>📊</div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-secondary)", marginBottom: 16 }}>
                  Grafana runs at localhost:3001
                </div>
                <a
                  href="http://localhost:3001"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                  style={{ textDecoration: "none", display: "inline-flex" }}
                >
                  Open Grafana ↗
                </a>
              </div>
            </div>
            <div className="card">
              <div className="card-title">⬡ Prometheus Metrics</div>
              <div style={{ padding: "20px 0", textAlign: "center" }}>
                <div style={{ fontSize: 40, marginBottom: 10 }}>📈</div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-secondary)", marginBottom: 16 }}>
                  Prometheus runs at localhost:9090
                </div>
                <a
                  href="http://localhost:9090"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-ghost"
                  style={{ textDecoration: "none", display: "inline-flex" }}
                >
                  Open Prometheus ↗
                </a>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
