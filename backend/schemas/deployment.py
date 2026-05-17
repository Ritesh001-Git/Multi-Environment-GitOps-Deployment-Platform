"""
schemas/deployment.py — Pydantic models for API input/output.
Keeps ORM models separate from API contracts.
"""
from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime
from typing import Optional
from models.deployment import DeploymentStatus, DeploymentEnvironment


# ── Request bodies ────────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    environment: DeploymentEnvironment = DeploymentEnvironment.LOCAL_K8S
    docker_image: Optional[str] = None

    @field_validator("repo_url")
    @classmethod
    def must_be_github(cls, v: str) -> str:
        if not v.startswith("https://github.com/"):
            raise ValueError("Only GitHub HTTPS URLs are supported.")
        return v.rstrip("/")


# ── Response bodies ───────────────────────────────────────────────────────────

class DeploymentOut(BaseModel):
    id: str
    repo_url: str
    repo_name: str
    branch: str
    commit_sha: Optional[str]
    docker_image: Optional[str]
    docker_tag: Optional[str]
    jenkins_build_number: Optional[int]
    jenkins_build_url: Optional[str]
    k8s_namespace: str
    k8s_deployment_name: Optional[str]
    status: DeploymentStatus
    environment: DeploymentEnvironment
    started_at: datetime
    finished_at: Optional[datetime]
    duration_seconds: Optional[float]
    triggered_by: str

    model_config = {"from_attributes": True}


class DeploymentListOut(BaseModel):
    total: int
    items: list[DeploymentOut]


class TriggerResponse(BaseModel):
    deployment_id: str
    jenkins_build_number: Optional[int]
    message: str
    status: DeploymentStatus


# ── Dashboard stats ───────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    running_deployments: int
    success_rate: float          # 0.0 – 100.0
    running_pods: int
    active_services: int
    avg_duration_seconds: Optional[float]


# ── Kubernetes schemas ────────────────────────────────────────────────────────

class PodOut(BaseModel):
    name: str
    namespace: str
    status: str                  # Running | Pending | Failed | Succeeded | Unknown
    ready: bool
    restart_count: int
    node_name: Optional[str]
    image: str
    image_tag: str
    age_seconds: int
    labels: dict[str, str]

    @property
    def age_display(self) -> str:
        s = self.age_seconds
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m"
        if s < 86400:
            return f"{s // 3600}h"
        return f"{s // 86400}d"


class K8sDeploymentOut(BaseModel):
    name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    image: str
    created_at: Optional[datetime]


class K8sOverview(BaseModel):
    pods: list[PodOut]
    deployments: list[K8sDeploymentOut]
    namespaces: list[str]
    total_pods: int
    running_pods: int
    pending_pods: int
    failed_pods: int