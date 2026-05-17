"""
models/deployment.py — SQLAlchemy ORM model for deployment tracking.
Every Jenkins pipeline run creates one row here.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base
import enum

from pydantic import BaseModel, field_validator
from typing import Optional


class DeploymentStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeploymentEnvironment(str, enum.Enum):
    LOCAL_K8S = "local-k8s"
    STAGING = "staging"
    PRODUCTION = "production"


class Deployment(Base):
    __tablename__ = "deployments"

    # ── Identity ─────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Source ────────────────────────────────────────────────────────────────
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), default="main")
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # ── Docker ────────────────────────────────────────────────────────────────
    docker_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    docker_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Jenkins ───────────────────────────────────────────────────────────────
    jenkins_build_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jenkins_build_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Kubernetes ────────────────────────────────────────────────────────────
    k8s_namespace: Mapped[str] = mapped_column(String(255), default="default")
    k8s_deployment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(DeploymentStatus), default=DeploymentStatus.QUEUED, index=True
    )
    environment: Mapped[DeploymentEnvironment] = mapped_column(
        SAEnum(DeploymentEnvironment), default=DeploymentEnvironment.LOCAL_K8S
    )

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Triggered by ──────────────────────────────────────────────────────────
    triggered_by: Mapped[str] = mapped_column(String(64), default="webhook")

    def calculate_duration(self) -> None:
        """Call when marking a deployment finished."""
        if self.started_at and self.finished_at:
            self.duration_seconds = (
                self.finished_at - self.started_at
            ).total_seconds()

    def finish(self, status: DeploymentStatus) -> None:
        self.status = status
        self.finished_at = datetime.now(timezone.utc)
        self.calculate_duration()

    @property
    def repo_name(self) -> str:
        """Extract 'user/repo' from full GitHub URL."""
        parts = self.repo_url.rstrip("/").split("/")
        return f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else self.repo_url
    
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
 