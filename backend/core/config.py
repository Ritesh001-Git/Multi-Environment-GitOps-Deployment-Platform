from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "GitOps Platform API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    GITHUB_WEBHOOK_SECRET: str = ""

    # ── Database ─────────────────────────────────────────────────────────────
    # SQLite (demo):  sqlite+aiosqlite:///./gitops.db
    # PostgreSQL:     postgresql+asyncpg://user:pass@host:5432/gitops
    DATABASE_URL: str = "sqlite+aiosqlite:///./gitops.db"

    # ── Jenkins ──────────────────────────────────────────────────────────────
    JENKINS_URL: str
    JENKINS_USER: str
    JENKINS_TOKEN: str
    JENKINS_JOB_NAME: str
    JENKINS_REQUEST_TIMEOUT_SECONDS: float = 10.0
    JENKINS_QUEUE_TIMEOUT_SECONDS: int = 120
    JENKINS_BUILD_TIMEOUT_SECONDS: int = 1800
    JENKINS_MAX_POLL_ERRORS: int = 6

    # ── Docker Hub ────────────────────────────────────────────────────────────
    DOCKERHUB_USER: str

    # ── Kubernetes ───────────────────────────────────────────────────────────
    # "in-cluster"  → use service account (when running inside a pod)
    # "kubeconfig"  → use ~/.kube/config (local dev / EC2)
    KUBE_MODE: str = "kubeconfig"
    KUBE_NAMESPACE: str
    KUBE_DEPLOYMENT_NAME: str
    KUBE_REQUEST_TIMEOUT_SECONDS: int = 10
    K3S_DEPLOY_HOST: str

    # ── Polling ───────────────────────────────────────────────────────────────
    # How often the background task polls Jenkins for running build status (seconds)
    POLL_INTERVAL_SECONDS: int = 5

    @field_validator(
        "JENKINS_URL",
        "JENKINS_USER",
        "JENKINS_TOKEN",
        "JENKINS_JOB_NAME",
        "DOCKERHUB_USER",
        "KUBE_NAMESPACE",
        "KUBE_DEPLOYMENT_NAME",
        "K3S_DEPLOY_HOST",
    )
    @classmethod
    def required_runtime_value(cls, value: str, info) -> str:
        value = value.strip()
        if not value or "REPLACE_" in value.upper() or "YOUR-" in value.upper():
            raise ValueError(f"{info.field_name} must be configured with a real value")
        return value.rstrip("/") if info.field_name == "JENKINS_URL" else value

    @field_validator("JENKINS_URL")
    @classmethod
    def valid_jenkins_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("JENKINS_URL must start with http:// or https://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
