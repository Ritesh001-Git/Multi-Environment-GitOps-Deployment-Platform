// types/index.ts — mirrors backend Pydantic schemas exactly

export type DeploymentStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export type DeploymentEnvironment = "local-k8s" | "staging" | "production";

export interface Deployment {
  id: string;
  repo_url: string;
  repo_name: string;
  branch: string;
  commit_sha: string | null;
  docker_image: string | null;
  docker_tag: string | null;
  jenkins_build_number: number | null;
  jenkins_build_url: string | null;
  k8s_namespace: string;
  k8s_deployment_name: string | null;
  status: DeploymentStatus;
  environment: DeploymentEnvironment;
  started_at: string;        // ISO datetime
  finished_at: string | null;
  duration_seconds: number | null;
  triggered_by: string;
}

export interface DeploymentListResponse {
  total: number;
  items: Deployment[];
}

export interface TriggerResponse {
  deployment_id: string;
  jenkins_build_number: number | null;
  message: string;
  status: DeploymentStatus;
}

export interface DeployRequest {
  repo_url: string;
  branch: string;
  environment: DeploymentEnvironment;
  docker_image?: string;
}

// ── Dashboard stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  total_deployments: number;
  successful_deployments: number;
  failed_deployments: number;
  running_deployments: number;
  success_rate: number;       // 0–100
  running_pods: number | null;
  active_services: number | null;
  kubernetes_available: boolean;
  kubernetes_error: string | null;
  avg_duration_seconds: number | null;
}

// ── Kubernetes ────────────────────────────────────────────────────────────────

export interface Pod {
  name: string;
  namespace: string;
  status: "Running" | "Pending" | "Failed" | "Succeeded" | "Unknown";
  ready: boolean;
  ready_containers: number;
  total_containers: number;
  restart_count: number;
  node_name: string | null;
  pod_ip: string | null;
  image: string;
  image_tag: string;
  age_seconds: number;
  labels: Record<string, string>;
}

export interface K8sDeployment {
  name: string;
  namespace: string;
  desired_replicas: number;
  ready_replicas: number;
  available_replicas: number;
  image: string;
  created_at: string | null;
}

export interface K8sOverview {
  pods: Pod[];
  deployments: K8sDeployment[];
  namespaces: string[];
  total_pods: number;
  running_pods: number;
  pending_pods: number;
  failed_pods: number;
}

// ── WebSocket status update ───────────────────────────────────────────────────

export interface DeploymentStatusUpdate {
  id: string;
  status: DeploymentStatus;
  jenkins_build_number: number | null;
  jenkins_build_url: string | null;
  started_at: string | null;
  duration_seconds: number | null;
  finished_at: string | null;
  error?: string;
}

// ── UI helpers ────────────────────────────────────────────────────────────────

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}
