"""
api/routes/deployments.py
REST + WebSocket endpoints for GitOps platform.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.database import get_db
from k8s.client import k8s_service
from models.deployment import DeploymentStatus
from schemas.deployment import (
    DashboardStats,
    DeployRequest,
    DeploymentListOut,
    DeploymentOut,
    K8sOverview,
    TriggerResponse,
)

from services import deployment_service as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=DashboardStats,
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
):
    return await svc.get_dashboard_stats(db)


# ─────────────────────────────────────────────────────────────────────────────
# Kubernetes Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/kubernetes/overview",
    response_model=K8sOverview,
)
async def k8s_overview(
    namespace: str = Query("gitops"),
):
    return k8s_service.get_overview(namespace)


@router.get("/kubernetes/pods")
async def list_pods(
    namespace: str = Query("gitops"),
):

    pods = k8s_service.get_pods(namespace)

    return {
        "namespace": namespace,
        "total": len(pods),
        "pods": [
            p.model_dump()
            for p in pods
        ],
    }


@router.get("/kubernetes/deployments")
async def list_k8s_deployments(
    namespace: str = Query("gitops"),
):

    deps = k8s_service.get_deployments(namespace)

    return {
        "deployments": [
            d.model_dump()
            for d in deps
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Webhook
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook/github")
async def github_webhook(
    request_body: dict,
    db: AsyncSession = Depends(get_db),
):

    ref = request_body.get("ref", "")

    branch = ref.replace(
        "refs/heads/",
        "",
    )

    repo_url = (
        request_body.get("repository", {})
        .get("clone_url", "")
    )

    if (
        not repo_url
        or not repo_url.startswith(
            "https://github.com/"
        )
    ):
        return {"status": "ignored"}

    payload = DeployRequest(
        repo_url=repo_url,
        branch=branch,
    )

    dep = await svc.create_deployment(
        db,
        payload,
    )

    dep.triggered_by = "webhook"

    await db.commit()

    # IMPORTANT FIX
    asyncio.create_task(
        svc.run_pipeline(dep.id)
    )

    logger.info(
        f"Webhook deployment started: "
        f"{dep.id}"
    )

    return {
        "status": "triggered",
        "deployment_id": dep.id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/{deployment_id}")
async def deployment_websocket(
    websocket: WebSocket,
    deployment_id: str,
):

    await websocket.accept()

    logger.info(
        f"WebSocket connected for deployment {deployment_id}"
    )

    try:

        while True:

            async with AsyncSessionLocal() as db:

                deployment = await svc.get_deployment(
                    db,
                    deployment_id,
                )

                if not deployment:

                    await websocket.send_json({
                        "error": "Deployment not found"
                    })

                    break

                await websocket.send_json({
                    "id": deployment.id,
                    "status": deployment.status.value,
                    "jenkins_build_number": deployment.jenkins_build_number,
                    "started_at": (
                        deployment.started_at.isoformat()
                        if deployment.started_at else None
                    ),
                    "finished_at": (
                        deployment.finished_at.isoformat()
                        if deployment.finished_at else None
                    ),
                    "duration_seconds": deployment.duration_seconds,
                })

                if deployment.status in [
                    DeploymentStatus.SUCCESS,
                    DeploymentStatus.FAILED,
                    DeploymentStatus.CANCELLED,
                ]:
                    break

            await asyncio.sleep(2)

    except WebSocketDisconnect:

        logger.info(
            f"WebSocket disconnected for deployment {deployment_id}"
        )

    except Exception as e:

        logger.error(
            f"WebSocket error for deployment "
            f"{deployment_id}: {e}"
        )

    finally:

        try:
            await websocket.close()
        except:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Deployment
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TriggerResponse,
    status_code=202,
)
async def trigger_deployment(
    payload: DeployRequest,
    db: AsyncSession = Depends(get_db),
):

    dep = await svc.create_deployment(
        db,
        payload,
    )

    await db.commit()

    # IMPORTANT FIX
    asyncio.create_task(
        svc.run_pipeline(dep.id)
    )

    logger.info(
        f"Deployment queued: {dep.id}"
    )

    return TriggerResponse(
        deployment_id=dep.id,
        jenkins_build_number=None,
        message="Deployment queued",
        status=dep.status,
    )


# ─────────────────────────────────────────────────────────────────────────────
# List Deployments
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DeploymentListOut,
)
async def list_deployments(
    limit: int = Query(
        50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    status: Optional[
        DeploymentStatus
    ] = Query(None),
    db: AsyncSession = Depends(get_db),
):

    total, items = (
        await svc.list_deployments(
            db,
            limit=limit,
            offset=offset,
            status=status,
        )
    )

    return DeploymentListOut(
        total=total,
        items=[
            _enrich(d)
            for d in items
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deployment Status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{deployment_id}/status")
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):

    dep = await svc.get_deployment(
        db,
        deployment_id,
    )

    if not dep:

        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    return {
        "id": dep.id,
        "status": dep.status,
        "jenkins_build_number":
            dep.jenkins_build_number,
        "jenkins_build_url":
            dep.jenkins_build_url,
        "duration_seconds":
            dep.duration_seconds,
        "finished_at":
            dep.finished_at,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Get Single Deployment
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{deployment_id}",
    response_model=DeploymentOut,
)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):

    dep = await svc.get_deployment(
        db,
        deployment_id,
    )

    if not dep:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Deployment "
                f"{deployment_id} "
                f"not found"
            ),
        )

    return _enrich(dep)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

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
