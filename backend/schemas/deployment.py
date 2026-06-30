"""
schemas/deployment.py — Pydantic models for API input/output.
Keeps ORM models separate from API contracts.
"""
import re

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from models.deployment import DeploymentStatus, DeploymentEnvironment


# ── Request bodies ────────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    repo_url: str = Field(max_length=512)
    branch: str = Field(default="main", min_length=1, max_length=255)
    environment: DeploymentEnvironment = DeploymentEnvironment.LOCAL_K8S
    docker_image: Optional[str] = None

    @field_validator("repo_url")
    @classmethod
    def must_be_github(cls, v: str) -> str:
        normalized = v.rstrip("/")
        if not re.fullmatch(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?",
            normalized,
        ):
            raise ValueError("Only GitHub HTTPS URLs are supported.")
        return normalized

    @field_validator("branch")
    @classmethod
    def valid_branch(cls, value: str) -> str:
        if ".." in value or not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
            raise ValueError("Branch contains unsupported characters.")
        return value

    @field_validator("docker_image")
    @classmethod
    def valid_docker_image(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not re.fullmatch(
            r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+",
            value,
        ):
            raise ValueError("Docker image must be a lowercase registry/repository name without a tag.")
        return value


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
    running_pods: Optional[int]
    active_services: Optional[int]
    kubernetes_available: bool = True
    kubernetes_error: Optional[str] = None
    avg_duration_seconds: Optional[float]


# ── Kubernetes schemas ────────────────────────────────────────────────────────

class PodOut(BaseModel):
    name: str
    namespace: str
    status: str                  # Running | Pending | Failed | Succeeded | Unknown
    ready: bool
    ready_containers: int
    total_containers: int
    restart_count: int
    node_name: Optional[str]
    pod_ip: Optional[str]
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
