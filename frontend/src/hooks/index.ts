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
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generationRef = useRef(0);

  const fetch = useCallback(async () => {
    const generation = generationRef.current;
    try {
      const data = await fetcher();
      if (generation === generationRef.current) {
        setState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (generation === generationRef.current) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: extractErrorMessage(err),
        }));
      }
    }
  }, [fetcher]);

  useEffect(() => {
    generationRef.current += 1;
    if (!enabled) return;
    let disposed = false;
    const poll = async () => {
      await fetch();
      if (!disposed) timerRef.current = setTimeout(poll, intervalMs);
    };
    poll();
    return () => {
      disposed = true;
      generationRef.current += 1;
      if (timerRef.current) clearTimeout(timerRef.current);
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
  const requestGeneration = useRef(0);

  const isTerminal = state.data?.id === id && (
    state.data?.status === "success" ||
    state.data?.status === "failed" ||
    state.data?.status === "cancelled"
  );

  const fetcher = useCallback(async (generation = requestGeneration.current): Promise<boolean> => {
    if (!id) return false;
    try {
      const data = await deploymentsApi.get(id);
      if (generation === requestGeneration.current) {
        setState({ data, loading: false, error: null });
      }
      return true;
    } catch (err) {
      if (generation === requestGeneration.current) {
        setState({ data: null, loading: false, error: extractErrorMessage(err) });
      }
      return false;
    }
  }, [id]);

  useEffect(() => {
    requestGeneration.current += 1;
    if (!id) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    if (isTerminal) return;
    setState((previous) => ({
      data: previous.data?.id === id ? previous.data : null,
      loading: true,
      error: null,
    }));
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const generation = requestGeneration.current;
    let consecutiveErrors = 0;
    const poll = async () => {
      const succeeded = await fetcher(generation);
      consecutiveErrors = succeeded ? 0 : consecutiveErrors + 1;
      if (!disposed && consecutiveErrors < 3) {
        timer = setTimeout(poll, pollMs);
      }
    };
    poll();
    return () => {
      disposed = true;
      requestGeneration.current += 1;
      if (timer) clearTimeout(timer);
    };
  }, [id, fetcher, isTerminal, pollMs]);

  return state;
}

// ── WebSocket hook — real-time updates for active deployment ─────────────────

export function useDeploymentSocket(deploymentId: string | null) {
  const [update, setUpdate] = useState<DeploymentStatusUpdate | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setUpdate(null);
    setConnected(false);
    if (!deploymentId) return;
    let disposed = false;
    let terminal = false;
    let attempts = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (disposed || terminal) return;
      const ws = createDeploymentSocket(
        deploymentId,
        (msg) => {
          if (msg.error && !msg.status) {
            terminal = true;
            setConnected(false);
            ws.close(1008, "deployment unavailable");
            return;
          }
          attempts = 0;
          setUpdate(msg);
          setConnected(true);
          terminal = ["success", "failed", "cancelled"].includes(msg.status);
          if (terminal) ws.close(1000, "deployment complete");
        },
        () => {
          setConnected(false);
          if (!disposed && !terminal) {
            const delay = Math.min(1000 * 2 ** attempts++, 15_000);
            retryTimer = setTimeout(connect, delay);
          }
        }
      );
      ws.onopen = () => {
        attempts = 0;
        setConnected(true);
      };
      wsRef.current = ws;
    };
    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close(1000, "component unmounted");
      wsRef.current = null;
    };
  }, [deploymentId]);

  return { update, connected };
}

// ── Kubernetes overview (polls every 15s) ─────────────────────────────────────

export function useK8sOverview(namespace = "gitops", pollMs = 15_000) {
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
