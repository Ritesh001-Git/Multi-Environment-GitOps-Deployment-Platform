"""
models/deployment.py — SQLAlchemy ORM model ONLY.
Pydantic schemas are in schemas/deployment.py.
"""

import uuid
import enum

from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Float,
    Enum as SAEnum,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from db.database import Base


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

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    repo_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
    )

    commit_sha: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    docker_image: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    docker_tag: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    jenkins_build_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    jenkins_build_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    k8s_namespace: Mapped[str] = mapped_column(
        String(255),
        default="default",
    )

    k8s_deployment_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(DeploymentStatus),
        default=DeploymentStatus.QUEUED,
        index=True,
    )

    environment: Mapped[DeploymentEnvironment] = mapped_column(
        SAEnum(DeploymentEnvironment),
        default=DeploymentEnvironment.LOCAL_K8S,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    triggered_by: Mapped[str] = mapped_column(
        String(64),
        default="webhook",
    )

    def calculate_duration(self) -> None:

        if self.started_at and self.finished_at:

            started = self.started_at
            finished = self.finished_at

            # SQLite may strip timezone info
            if started.tzinfo is None:
                started = started.replace(
                    tzinfo=timezone.utc
                )

            if finished.tzinfo is None:
                finished = finished.replace(
                    tzinfo=timezone.utc
                )

            self.duration_seconds = (
                finished - started
            ).total_seconds()

    def finish(
        self,
        status: DeploymentStatus,
    ) -> None:

        self.status = status

        self.finished_at = datetime.now(
            timezone.utc
        )

        self.calculate_duration()

    @property
    def repo_name(self) -> str:

        parts = (
            self.repo_url
            .rstrip("/")
            .split("/")
        )

        return (
            f"{parts[-2]}/{parts[-1]}"
            if len(parts) >= 2
            else self.repo_url
        )
