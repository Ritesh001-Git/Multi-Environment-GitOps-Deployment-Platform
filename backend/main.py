"""
GitOps Platform - FastAPI Backend
Receives deploy requests, triggers Jenkins, tracks status.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import httpx
import uuid
import time
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitOps Platform API", version="1.0.0")

# ─── CORS (allow React dev server + EC2 public IP) ───────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config (set via environment variables on EC2) ───────────────────────────
JENKINS_URL      = os.getenv("JENKINS_URL",      "http://localhost:8080")
JENKINS_USER     = os.getenv("JENKINS_USER",     "admin")
JENKINS_TOKEN    = os.getenv("JENKINS_TOKEN",    "")   # Jenkins API token
JENKINS_JOB_NAME = os.getenv("JENKINS_JOB",     "gitops-deploy")
DOCKERHUB_USER   = os.getenv("DOCKERHUB_USER",  "your-dockerhub-user")

# ─── In-memory job store (replace with DB in production) ─────────────────────
jobs: dict[str, dict] = {}

# ─── Models ──────────────────────────────────────────────────────────────────
class DeployRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    environment: str = "local-k8s"
    docker_image: Optional[str] = None

class DeployResponse(BaseModel):
    job_id: str
    build_number: Optional[int]
    message: str
    jenkins_url: Optional[str]

class JobStatus(BaseModel):
    job_id: str
    status: str          # queued | running | success | failed
    current_stage: str
    build_number: Optional[int]
    repo_url: str
    branch: str
    started_at: float
    finished_at: Optional[float]
    logs_url: Optional[str]

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "GitOps Platform API", "status": "ok", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/api/deploy", response_model=DeployResponse)
async def trigger_deploy(payload: DeployRequest, background_tasks: BackgroundTasks):
    """
    Accepts a GitHub repo URL, triggers Jenkins pipeline.
    Returns job_id for polling.
    """
    if not payload.repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub HTTPS URLs are supported.")

    job_id = str(uuid.uuid4())[:8]
    docker_image = payload.docker_image or f"{DOCKERHUB_USER}/{_repo_slug(payload.repo_url)}"

    # Store job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "current_stage": "clone",
        "build_number": None,
        "repo_url": payload.repo_url,
        "branch": payload.branch,
        "environment": payload.environment,
        "docker_image": docker_image,
        "started_at": time.time(),
        "finished_at": None,
        "logs_url": None,
    }

    # Trigger Jenkins in background
    background_tasks.add_task(_trigger_jenkins, job_id, payload, docker_image)

    logger.info(f"Deploy job {job_id} queued for {payload.repo_url}")
    return DeployResponse(
        job_id=job_id,
        build_number=None,
        message="Pipeline queued",
        jenkins_url=f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/",
    )


@app.get("/api/deploy/{job_id}/status", response_model=JobStatus)
def get_status(job_id: str):
    """Poll deployment status."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return JobStatus(**job)


@app.get("/api/deploy/{job_id}/logs")
async def get_logs(job_id: str):
    """Proxy Jenkins console log."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job["build_number"]:
        return {"logs": "Build not started yet."}

    logs_url = (
        f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/"
        f"{job['build_number']}/consoleText"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                logs_url,
                auth=(JENKINS_USER, JENKINS_TOKEN),
                timeout=10,
            )
            return {"logs": resp.text}
    except Exception as e:
        return {"logs": f"Could not fetch logs: {e}"}


@app.post("/api/webhook/github")
async def github_webhook(request: Request):
    """
    GitHub webhook endpoint.
    Configure in GitHub repo → Settings → Webhooks.
    Set payload URL to: http://<EC2-IP>:8000/api/webhook/github
    """
    payload = await request.json()
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    repo_url = payload.get("repository", {}).get("clone_url", "")

    if not repo_url:
        return {"status": "ignored", "reason": "no repo url"}

    logger.info(f"Webhook received: {repo_url} branch={branch}")

    # Auto-trigger deploy
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "current_stage": "clone",
        "build_number": None,
        "repo_url": repo_url,
        "branch": branch,
        "environment": "local-k8s",
        "docker_image": f"{DOCKERHUB_USER}/{_repo_slug(repo_url)}",
        "started_at": time.time(),
        "finished_at": None,
        "logs_url": None,
    }

    deploy_req = DeployRequest(repo_url=repo_url, branch=branch)
    # Fire and forget
    import asyncio
    asyncio.create_task(
        _trigger_jenkins(job_id, deploy_req, jobs[job_id]["docker_image"])
    )

    return {"status": "triggered", "job_id": job_id}


@app.get("/api/jobs")
def list_jobs(limit: int = 20):
    """Return all recent jobs."""
    sorted_jobs = sorted(jobs.values(), key=lambda j: j["started_at"], reverse=True)
    return {"jobs": sorted_jobs[:limit]}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _repo_slug(repo_url: str) -> str:
    """github.com/user/repo -> user-repo"""
    parts = repo_url.rstrip("/").split("/")
    return f"{parts[-2]}-{parts[-1]}".lower() if len(parts) >= 2 else "app"


async def _trigger_jenkins(job_id: str, payload: DeployRequest, docker_image: str):
    """
    Call Jenkins remote trigger API.
    Falls back gracefully if Jenkins is not running.
    """
    jobs[job_id]["status"] = "running"
    jobs[job_id]["current_stage"] = "clone"

    params = {
        "REPO_URL":     payload.repo_url,
        "BRANCH":       payload.branch,
        "DOCKER_IMAGE": docker_image,
        "ENVIRONMENT":  payload.environment,
    }

    trigger_url = (
        f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/buildWithParameters"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                trigger_url,
                params=params,
                auth=(JENKINS_USER, JENKINS_TOKEN),
                timeout=10,
            )
            if resp.status_code in (200, 201):
                # Extract build number from Location header
                location = resp.headers.get("Location", "")
                build_num = _extract_build_number(location)
                jobs[job_id]["build_number"] = build_num
                jobs[job_id]["logs_url"] = (
                    f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/{build_num}/console"
                    if build_num else None
                )
                logger.info(f"Jenkins build #{build_num} started for job {job_id}")
            else:
                logger.warning(f"Jenkins returned {resp.status_code} for job {job_id}")
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["finished_at"] = time.time()

    except httpx.ConnectError:
        logger.warning(f"Jenkins not reachable for job {job_id}. Is Jenkins running?")
        # Mark as failed so frontend knows
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["finished_at"] = time.time()

    except Exception as e:
        logger.error(f"Unexpected error triggering Jenkins: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["finished_at"] = time.time()


def _extract_build_number(location: str) -> Optional[int]:
    """Parse build number from Jenkins Location header."""
    # Location: http://localhost:8080/queue/item/42/
    try:
        parts = [p for p in location.rstrip("/").split("/") if p]
        return int(parts[-1])
    except (ValueError, IndexError):
        return None
