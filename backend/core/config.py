"""
core/config.py — All environment variables in one place.
Copy .env.example to .env and fill in real values.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "GitOps Platform API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database ─────────────────────────────────────────────────────────────
    # SQLite (demo):  sqlite+aiosqlite:///./gitops.db
    # PostgreSQL:     postgresql+asyncpg://user:pass@host:5432/gitops
    DATABASE_URL: str = "sqlite+aiosqlite:///./gitops.db"

    # ── Jenkins ──────────────────────────────────────────────────────────────
    JENKINS_URL: str = "http://localhost:8080"
    JENKINS_USER: str = "admin"
    JENKINS_TOKEN: str = ""
    JENKINS_JOB_NAME: str = "gitops-deploy"

    # ── Docker Hub ────────────────────────────────────────────────────────────
    DOCKERHUB_USER: str = "your-dockerhub-user"

    # ── Kubernetes ───────────────────────────────────────────────────────────
    # "in-cluster"  → use service account (when running inside a pod)
    # "kubeconfig"  → use ~/.kube/config (local dev / EC2)
    KUBE_MODE: str = "kubeconfig"
    KUBE_NAMESPACE: str = "default"

    # ── Polling ───────────────────────────────────────────────────────────────
    # How often the background task polls Jenkins for running build status (seconds)
    POLL_INTERVAL_SECONDS: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()