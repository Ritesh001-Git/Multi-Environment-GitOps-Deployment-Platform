// hooks/index.ts — All data-fetching hooks in one file

import { useState, useEffect, useCallback, useRef } from "react";
import {
  dashboardApi,
  deploymentsApi,
  kubernetesApi,
  createDeploymentSocket,
  extractErrorMessage,
} from "../api/client";
import type {
  DashboardStats,
  Deployment,
  DeploymentListResponse,
  K8sOverview,
  AsyncState,
  DeploymentStatusUpdate,
} from "../types";

// ── Generic polling hook ──────────────────────────────────────────────────────

function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true
): AsyncState<T> & { refresh: () => void } {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await fetcher();
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: extractErrorMessage(err),
      }));
    }
  }, [fetcher]);

  useEffect(() => {
    if (!enabled) return;
    fetch();
    timerRef.current = setInterval(fetch, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetch, intervalMs, enabled]);

  return { ...state, refresh: fetch };
}

// ── Dashboard stats (polls every 10s) ────────────────────────────────────────

export function useDashboardStats(pollMs = 10_000) {
  const fetcher = useCallback(() => dashboardApi.getStats(), []);
  return usePolling<DashboardStats>(fetcher, pollMs);
}

// ── Deployment list (polls every 8s) ─────────────────────────────────────────

export function useDeployments(
  params?: { limit?: number; offset?: number; status?: string },
  pollMs = 8_000
) {
  const fetcher = useCallback(
    () => deploymentsApi.list(params),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(params)]
  );
  return usePolling<DeploymentListResponse>(fetcher, pollMs);
}

// ── Single deployment (polls every 4s while running) ─────────────────────────

export function useDeployment(id: string | null, pollMs = 4_000) {
  const [state, setState] = useState<AsyncState<Deployment>>({
    data: null,
    loading: !!id,
    error: null,
  });

  const isTerminal =
    state.data?.status === "success" ||
    state.data?.status === "failed" ||
    state.data?.status === "cancelled";

  const fetcher = useCallback(async () => {
    if (!id) return;
    try {
      const data = await deploymentsApi.get(id);
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: extractErrorMessage(err) });
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    fetcher();
    if (isTerminal) return;
    const timer = setInterval(fetcher, pollMs);
    return () => clearInterval(timer);
  }, [id, fetcher, isTerminal, pollMs]);

  return state;
}

// ── WebSocket hook — real-time updates for active deployment ─────────────────

export function useDeploymentSocket(deploymentId: string | null) {
  const [update, setUpdate] = useState<DeploymentStatusUpdate | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!deploymentId) return;

    const ws = createDeploymentSocket(
      deploymentId,
      (msg) => {
        setUpdate(msg);
        setConnected(true);
      },
      () => setConnected(false)
    );

    ws.onopen = () => setConnected(true);
    wsRef.current = ws;

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [deploymentId]);

  return { update, connected };
}

// ── Kubernetes overview (polls every 15s) ─────────────────────────────────────

export function useK8sOverview(namespace = "default", pollMs = 15_000) {
  const fetcher = useCallback(
    () => kubernetesApi.getOverview(namespace),
    [namespace]
  );
  return usePolling<K8sOverview>(fetcher, pollMs);
}

// ── Trigger deployment hook ───────────────────────────────────────────────────

export function useTriggerDeployment() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);

  const trigger = useCallback(
    async (payload: import("../types").DeployRequest) => {
      setLoading(true);
      setError(null);
      setDeploymentId(null);
      try {
        const result = await deploymentsApi.trigger(payload);
        setDeploymentId(result.deployment_id);
        return result;
      } catch (err) {
        const msg = extractErrorMessage(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { trigger, loading, error, deploymentId };
}