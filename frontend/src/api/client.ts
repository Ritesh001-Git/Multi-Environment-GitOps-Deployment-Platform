// api/client.ts — Axios instance + typed API methods
import axios, { AxiosError } from "axios";
import type {
  DashboardStats,
  Deployment,
  DeploymentListResponse,
  DeployRequest,
  TriggerResponse,
  K8sOverview,
  Pod,
} from "../types";

// ── Axios instance ────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// Global error normaliser — turns any axios error into a readable string
export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred.";
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const { data } = await apiClient.get<DashboardStats>("/deployments/stats");
    return data;
  },
};

// ── Deployments ───────────────────────────────────────────────────────────────

export const deploymentsApi = {
  trigger: async (payload: DeployRequest): Promise<TriggerResponse> => {
    const { data } = await apiClient.post<TriggerResponse>(
      "/deployments",
      payload
    );
    return data;
  },

  list: async (params?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<DeploymentListResponse> => {
    const { data } = await apiClient.get<DeploymentListResponse>(
      "/deployments",
      { params }
    );
    return data;
  },

  get: async (id: string): Promise<Deployment> => {
    const { data } = await apiClient.get<Deployment>(`/deployments/${id}`);
    return data;
  },

  getStatus: async (id: string) => {
    const { data } = await apiClient.get(`/deployments/${id}/status`);
    return data;
  },
};

// ── Kubernetes ────────────────────────────────────────────────────────────────

export const kubernetesApi = {
  getOverview: async (namespace = "default"): Promise<K8sOverview> => {
    const { data } = await apiClient.get<K8sOverview>(
      "/deployments/kubernetes/overview",
      { params: { namespace } }
    );
    return data;
  },

  getPods: async (namespace = "default"): Promise<Pod[]> => {
    const { data } = await apiClient.get<{ pods: Pod[] }>(
      "/deployments/kubernetes/pods",
      { params: { namespace } }
    );
    return data.pods;
  },
};

// ── WebSocket factory ─────────────────────────────────────────────────────────

export function createDeploymentSocket(
  deploymentId: string,
  onMessage: (update: import("../types").DeploymentStatusUpdate) => void,
  onClose?: () => void
): WebSocket {
  const wsBase = BASE_URL.replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/api/deployments/ws/${deploymentId}`);

  ws.onmessage = (event) => {
    try {
      const update = JSON.parse(event.data);
      onMessage(update);
    } catch {
      console.error("WS parse error", event.data);
    }
  };

  ws.onclose = () => onClose?.();
  ws.onerror = (e) => console.error("WS error", e);

  return ws;
}