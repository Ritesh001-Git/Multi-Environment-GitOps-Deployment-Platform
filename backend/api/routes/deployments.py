"""
api/routes/deployments.py — All REST + WebSocket endpoints.

Route ordering is critical in FastAPI — specific static routes must come
BEFORE parameterised /{id} routes or FastAPI will shadow them.

Correct order:
  /stats
  /kubernetes/overview      ← must be before /{deployment_id}
  /kubernetes/pods          ← must be before /{deployment_id}
  /kubernetes/deployments   ← must be before /{deployment_id}
  /webhook/github           ← must be before /{deployment_id}
  /ws/{deployment_id}       ← WebSocket
  POST ""                   ← create
  GET  ""                   ← list
  GET  /{deployment_id}     ← single lookup  (LAST among GETs)
  GET  /{deployment_id}/status
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, BackgroundTasks,
    Query, WebSocket, WebSocketDisconnect,
)
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.deployment import DeploymentStatus
from schemas.deployment import (
    DeployRequest, DeploymentOut, DeploymentListOut,
    TriggerResponse, DashboardStats, K8sOverview,
)
from services import deployment_service as svc
from k8s.client import k8s_service
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 1. Dashboard stats ────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats, summary="Dashboard overview cards")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await svc.get_dashboard_stats(db)


# ── 2. Kubernetes routes (BEFORE /{deployment_id}) ───────────────────────────

@router.get("/kubernetes/overview", response_model=K8sOverview, summary="Full K8s overview")
async def k8s_overview(
    namespace: str = Query("default", description="Kubernetes namespace or 'all'"),
):
    return k8s_service.get_overview(namespace)


@router.get("/kubernetes/pods", summary="List pods")
async def list_pods(namespace: str = Query("default")):
    pods = k8s_service.get_pods(namespace)
    return {"namespace": namespace, "total": len(pods), "pods": [p.model_dump() for p in pods]}


@router.get("/kubernetes/deployments", summary="List K8s deployments")
async def list_k8s_deployments(namespace: str = Query("default")):
    deps = k8s_service.get_deployments(namespace)
    return {"deployments": [d.model_dump() for d in deps]}


# ── 3. GitHub webhook (static path — before /{deployment_id}) ────────────────

@router.post("/webhook/github", summary="GitHub push webhook")
async def github_webhook(
    request_body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    ref = request_body.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    repo_url = request_body.get("repository", {}).get("clone_url", "")

    if not repo_url or not repo_url.startswith("https://github.com/"):
        return {"status": "ignored"}

    payload = DeployRequest(repo_url=repo_url, branch=branch)
    dep = await svc.create_deployment(db, payload)
    dep.triggered_by = "webhook"
    await db.commit()

    background_tasks.add_task(svc.run_pipeline, dep.id)
    logger.info(f"Webhook triggered deployment {dep.id} for {repo_url}@{branch}")
    return {"status": "triggered", "deployment_id": dep.id}


# ── 4. WebSocket (before /{deployment_id}) ────────────────────────────────────

@router.websocket("/ws/{deployment_id}")
async def deployment_websocket(
    websocket: WebSocket,
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()
    try:
        while True:
            dep = await svc.get_deployment(db, deployment_id)
            if not dep:
                await websocket.send_text(json.dumps({"error": "not_found"}))
                break

            payload = {
                "id": dep.id,
                "status": dep.status.value,
                "jenkins_build_number": dep.jenkins_build_number,
                "jenkins_build_url": dep.jenkins_build_url,
                "duration_seconds": dep.duration_seconds,
                "finished_at": dep.finished_at.isoformat() if dep.finished_at else None,
            }
            await websocket.send_text(json.dumps(payload))

            if dep.status in (
                DeploymentStatus.SUCCESS,
                DeploymentStatus.FAILED,
                DeploymentStatus.CANCELLED,
            ):
                break

            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for deployment {deployment_id}")
    finally:
        await websocket.close()


# ── 5. Deployments collection (create + list) ─────────────────────────────────

@router.post("", response_model=TriggerResponse, status_code=202, summary="Trigger new deployment")
async def trigger_deployment(
    payload: DeployRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    dep = await svc.create_deployment(db, payload)
    await db.commit()
    background_tasks.add_task(svc.run_pipeline, dep.id)
    logger.info(f"Deployment {dep.id} queued for {payload.repo_url}")
    return TriggerResponse(
        deployment_id=dep.id,
        jenkins_build_number=None,
        message="Deployment queued",
        status=dep.status,
    )


@router.get("", response_model=DeploymentListOut, summary="List deployment history")
async def list_deployments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[DeploymentStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    total, items = await svc.list_deployments(db, limit=limit, offset=offset, status=status)
    return DeploymentListOut(total=total, items=[_enrich(d) for d in items])


# ── 6. Single deployment lookup (/{id} routes — MUST come last) ──────────────

@router.get("/{deployment_id}/status", summary="Poll deployment status (lightweight)")
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    dep = await svc.get_deployment(db, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Not found.")
    return {
        "id": dep.id,
        "status": dep.status,
        "jenkins_build_number": dep.jenkins_build_number,
        "jenkins_build_url": dep.jenkins_build_url,
        "duration_seconds": dep.duration_seconds,
        "finished_at": dep.finished_at,
    }


@router.get("/{deployment_id}", response_model=DeploymentOut, summary="Get single deployment")
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    dep = await svc.get_deployment(db, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found.")
    return _enrich(dep)


# ── Helper ────────────────────────────────────────────────────────────────────

def _enrich(dep) -> DeploymentOut:
    return DeploymentOut(
        id=dep.id,
        repo_url=dep.repo_url,
        repo_name=dep.repo_name,
        branch=dep.branch,
        commit_sha=dep.commit_sha,
        docker_image=dep.docker_image,
        docker_tag=dep.docker_tag,
        jenkins_build_number=dep.jenkins_build_number,
        jenkins_build_url=dep.jenkins_build_url,
        k8s_namespace=dep.k8s_namespace,
        k8s_deployment_name=dep.k8s_deployment_name,
        status=dep.status,
        environment=dep.environment,
        started_at=dep.started_at,
        finished_at=dep.finished_at,
        duration_seconds=dep.duration_seconds,
        triggered_by=dep.triggered_by,
    )