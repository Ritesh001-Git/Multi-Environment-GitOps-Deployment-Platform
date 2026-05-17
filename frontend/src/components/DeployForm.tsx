// components/dashboard/DeployForm.tsx
// Triggers real Jenkins builds via the backend API

import React, { useState } from "react";
import { useTriggerDeployment } from "../hooks";
import { Spinner } from "./common/UI";
import type { DeploymentEnvironment } from "../types";

interface Props {
  onDeploymentStarted?: (deploymentId: string) => void;
}

export default function DeployForm({ onDeploymentStarted }: Props) {
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [environment, setEnvironment] = useState<DeploymentEnvironment>("local-k8s");
  const [dockerImage, setDockerImage] = useState("");

  const { trigger, loading, error } = useTriggerDeployment();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await trigger({
        repo_url: repoUrl,
        branch,
        environment,
        docker_image: dockerImage || undefined,
      });
      onDeploymentStarted?.(result.deployment_id);
      setRepoUrl("");
    } catch {
      // error is already set in the hook
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-900 mb-4">Deploy Repository</h3>

      <div className="space-y-3">
        {/* Repo URL */}
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1">
            GitHub Repository URL *
          </label>
          <input
            type="url"
            required
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/username/repo"
            disabled={loading}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50 disabled:bg-gray-50"
          />
        </div>

        {/* Branch + Environment */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">
              Branch
            </label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              disabled={loading}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">
              Environment
            </label>
            <select
              value={environment}
              onChange={(e) => setEnvironment(e.target.value as DeploymentEnvironment)}
              disabled={loading}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50"
            >
              <option value="local-k8s">Local Kubernetes</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
        </div>

        {/* Docker image override */}
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1">
            Docker Image Name{" "}
            <span className="font-normal text-gray-400">(optional — auto-generated if blank)</span>
          </label>
          <input
            type="text"
            value={dockerImage}
            onChange={(e) => setDockerImage(e.target.value)}
            placeholder="dockerhub-user/image-name"
            disabled={loading}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50"
          />
        </div>

        {/* Error */}
        {error && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            ✗ {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading || !repoUrl}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white font-semibold py-2.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
        >
          {loading ? (
            <>
              <Spinner size="sm" />
              Triggering Jenkins…
            </>
          ) : (
            "⚡ Deploy Now"
          )}
        </button>
      </div>
    </form>
  );
}