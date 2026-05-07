import { useState } from "react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function DeployForm({ onDeploy }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [environment, setEnvironment] = useState("local-k8s");
  const [dockerImage, setDockerImage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!repoUrl.trim()) {
      setError("Repository URL is required.");
      return;
    }
    if (!repoUrl.startsWith("https://github.com/")) {
      setError("Please enter a valid GitHub HTTPS URL.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          branch,
          environment,
          docker_image: dockerImage || undefined,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Deployment failed.");
        setLoading(false);
        return;
      }

      onDeploy({
        jobId: data.job_id,
        repoUrl,
        branch,
        environment,
        buildNumber: data.build_number,
      });
    } catch (err) {
      setError("Cannot reach backend. Is it running on port 8000?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-title">⚡ Trigger Deployment</div>
      <div className="deploy-form">

        <div>
          <label className="field-label">GitHub Repository URL *</label>
          <input
            className="input"
            placeholder="https://github.com/username/repo"
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="field-row">
          <div>
            <label className="field-label">Branch</label>
            <input
              className="input"
              placeholder="main"
              value={branch}
              onChange={e => setBranch(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className="field-label">Environment</label>
            <select
              className="select"
              value={environment}
              onChange={e => setEnvironment(e.target.value)}
              disabled={loading}
            >
              <option value="local-k8s">Local Kubernetes</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
        </div>

        <div>
          <label className="field-label">Docker Image Name (optional)</label>
          <input
            className="input"
            placeholder="dockerhub-user/image-name"
            value={dockerImage}
            onChange={e => setDockerImage(e.target.value)}
            disabled={loading}
          />
        </div>

        {error && (
          <div style={{
            background: "rgba(244,63,94,0.1)",
            border: "1px solid rgba(244,63,94,0.3)",
            borderRadius: 8,
            padding: "10px 14px",
            fontFamily: "var(--mono)",
            fontSize: 12,
            color: "var(--danger)",
          }}>
            ✗ {error}
          </div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? (
            <>
              <div className="spinner" />
              Triggering Jenkins...
            </>
          ) : (
            <>⚡ Deploy Now</>
          )}
        </button>

      </div>
    </div>
  );
}
