"""
services/deployment_service.py — Business logic layer.
Handles Jenkins calls, DB writes, status polling, and Prometheus metrics.
"""

import logging
import uuid
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.deployment import Deployment, DeploymentStatus
from schemas.deployment import DeployRequest, DashboardStats
from k8s.client import k8s_service

from metrics import (
    deployments_total,
    deployments_success,
    deployments_failed,
    deployment_duration,
    active_deployments,
    jenkins_builds_triggered,
    jenkins_build_duration,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Jenkins helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jenkins_auth() -> tuple[str, str]:
    return settings.JENKINS_USER, settings.JENKINS_TOKEN


async def _trigger_jenkins_build(
    http: httpx.AsyncClient,
    deployment: Deployment,
) -> Optional[int]:
    """
    Trigger Jenkins buildWithParameters.
    Returns Jenkins queue item ID.
    """

    url = f"{settings.JENKINS_URL}/job/{settings.JENKINS_JOB_NAME}/buildWithParameters"

    params = {
        "REPO_URL": deployment.repo_url,
        "BRANCH": deployment.branch,
        "DOCKER_IMAGE": deployment.docker_image or "",
        "ENVIRONMENT": deployment.environment.value,
    }

    try:
        response = await http.post(
            url,
            params=params,
            auth=_jenkins_auth(),
            timeout=10,
        )

        if response.status_code in (200, 201):

            location = response.headers.get("Location", "")

            # Extract queue item number
            parts = [
                p for p in location.rstrip("/").split("/")
                if p.isdigit()
            ]

            return int(parts[-1]) if parts else None

        logger.warning(f"Jenkins returned {response.status_code}")
        return None

    except httpx.ConnectError:
        logger.error("Jenkins not reachable")
        return None

    except Exception as e:
        logger.error(f"Jenkins trigger failed: {e}")
        return None


async def _resolve_build_number(
    http: httpx.AsyncClient,
    queue_item_id: int,
) -> Optional[int]:
    """
    Jenkins assigns build number asynchronously.
    Poll queue item until build number appears.
    """

    url = f"{settings.JENKINS_URL}/queue/item/{queue_item_id}/api/json"

    for _ in range(20):

        await asyncio.sleep(1)

        try:
            response = await http.get(
                url,
                auth=_jenkins_auth(),
                timeout=5,
            )

            data = response.json()

            executable = data.get("executable")

            if executable:
                return executable.get("number")

        except Exception:
            pass

    return None


async def _poll_jenkins_status(build_number: int) -> str:
    """
    Returns:
    - running
    - success
    - failed
    """

    url = (
        f"{settings.JENKINS_URL}/job/"
        f"{settings.JENKINS_JOB_NAME}/"
        f"{build_number}/api/json"
    )

    async with httpx.AsyncClient() as http:

        try:
            response = await http.get(
                url,
                auth=_jenkins_auth(),
                timeout=5,
            )

            data = response.json()

            building = data.get("building", False)
            result = data.get("result")

            if building:
                return "running"

            if result == "SUCCESS":
                return "success"

            return "failed"

        except Exception as e:
            logger.error(f"Jenkins poll error: {e}")
            return "running"


# ─────────────────────────────────────────────────────────────────────────────
# CRUD helpers
# ─────────────────────────────────────────────────────────────────────────────

async def create_deployment(
    db: AsyncSession,
    payload: DeployRequest,
) -> Deployment:

    repo_parts = payload.repo_url.rstrip("/").split("/")

    image_name = payload.docker_image or (
        f"{settings.DOCKERHUB_USER}/"
        f"{repo_parts[-2]}-{repo_parts[-1]}".lower()
        if len(repo_parts) >= 2
        else f"{settings.DOCKERHUB_USER}/app"
    )

    deployment = Deployment(
        id=str(uuid.uuid4()),
        repo_url=payload.repo_url,
        branch=payload.branch,
        environment=payload.environment,
        docker_image=image_name,
        k8s_namespace=settings.KUBE_NAMESPACE,
        status=DeploymentStatus.QUEUED,
        triggered_by="api",
    )

    db.add(deployment)

    await db.flush()

    return deployment


async def get_deployment(
    db: AsyncSession,
    deployment_id: str,
) -> Optional[Deployment]:

    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id
        )
    )

    return result.scalar_one_or_none()


async def list_deployments(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status: Optional[DeploymentStatus] = None,
) -> tuple[int, list[Deployment]]:

    query = select(Deployment)

    if status:
        query = query.where(
            Deployment.status == status
        )

    query = query.order_by(
        desc(Deployment.started_at)
    )

    count_query = select(func.count()).select_from(
        query.subquery()
    )

    total = (
        await db.execute(count_query)
    ).scalar_one()

    items = (
        await db.execute(
            query.offset(offset).limit(limit)
        )
    ).scalars().all()

    return total, list(items)


async def get_dashboard_stats(
    db: AsyncSession,
) -> DashboardStats:

    rows = (
        await db.execute(
            select(
                Deployment.status,
                func.count(Deployment.id)
            ).group_by(Deployment.status)
        )
    ).all()

    counts = {row[0]: row[1] for row in rows}

    total = sum(counts.values())

    successful = counts.get(
        DeploymentStatus.SUCCESS,
        0
    )

    failed = counts.get(
        DeploymentStatus.FAILED,
        0
    )

    running = (
        counts.get(DeploymentStatus.RUNNING, 0)
        + counts.get(DeploymentStatus.QUEUED, 0)
    )

    success_rate = (
        round((successful / total) * 100, 1)
        if total > 0
        else 0.0
    )

    avg_duration = (
        await db.execute(
            select(
                func.avg(
                    Deployment.duration_seconds
                )
            ).where(
                Deployment.duration_seconds.isnot(None)
            )
        )
    ).scalar_one_or_none()

    running_pods = k8s_service.get_running_pod_count(
        settings.KUBE_NAMESPACE
    )

    active_services = k8s_service.get_active_service_count(
        settings.KUBE_NAMESPACE
    )

    return DashboardStats(
        total_deployments=total,
        successful_deployments=successful,
        failed_deployments=failed,
        running_deployments=running,
        success_rate=success_rate,
        running_pods=running_pods,
        active_services=active_services,
        avg_duration_seconds=(
            round(avg_duration, 1)
            if avg_duration
            else None
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline task
# ─────────────────────────────────────────────────────────────────────────────

async def run_pipeline(deployment_id: str) -> None:
    """
    Full deployment pipeline orchestration.

    1. Trigger Jenkins
    2. Resolve build number
    3. Poll Jenkins
    4. Update DB
    5. Emit Prometheus metrics
    """

    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:

        deployment = await get_deployment(
            db,
            deployment_id,
        )

        if not deployment:
            return

        # ─────────────────────────────────────────
        # Metrics: deployment started
        # ─────────────────────────────────────────

        deployments_total.labels(
            environment=deployment.environment.value,
            triggered_by=deployment.triggered_by,
        ).inc()

        active_deployments.labels(
            environment=deployment.environment.value
        ).inc()

        pipeline_start = time.time()

        async with httpx.AsyncClient() as http:

            deployment.status = DeploymentStatus.RUNNING

            await db.commit()

            # ─────────────────────────────────────
            # Trigger Jenkins
            # ─────────────────────────────────────

            queue_id = await _trigger_jenkins_build(
                http,
                deployment,
            )

            jenkins_builds_triggered.labels(
                job_name=settings.JENKINS_JOB_NAME
            ).inc()

            # ─────────────────────────────────────
            # Trigger failed
            # ─────────────────────────────────────

            if queue_id is None:

                deployment.finish(
                    DeploymentStatus.FAILED
                )

                await db.commit()

                duration = time.time() - pipeline_start

                deployments_failed.labels(
                    environment=deployment.environment.value
                ).inc()

                active_deployments.labels(
                    environment=deployment.environment.value
                ).dec()

                deployment_duration.labels(
                    environment=deployment.environment.value,
                    status="failed",
                ).observe(duration)

                return

            # ─────────────────────────────────────
            # Resolve Jenkins build number
            # ─────────────────────────────────────

            build_number = await _resolve_build_number(
                http,
                queue_id,
            )

            if build_number:

                deployment.jenkins_build_number = build_number

                deployment.jenkins_build_url = (
                    f"{settings.JENKINS_URL}/job/"
                    f"{settings.JENKINS_JOB_NAME}/"
                    f"{build_number}/"
                )

                await db.commit()

            else:

                deployment.finish(
                    DeploymentStatus.FAILED
                )

                await db.commit()

                deployments_failed.labels(
                    environment=deployment.environment.value
                ).inc()

                active_deployments.labels(
                    environment=deployment.environment.value
                ).dec()

                return

            # ─────────────────────────────────────
            # Poll Jenkins build
            # ─────────────────────────────────────

            while True:

                await asyncio.sleep(
                    settings.POLL_INTERVAL_SECONDS
                )

                jenkins_status = await _poll_jenkins_status(
                    build_number
                )

                # ─────────────────────────────────
                # SUCCESS
                # ─────────────────────────────────

                if jenkins_status == "success":

                    deployment.finish(
                        DeploymentStatus.SUCCESS
                    )

                    deployment.k8s_deployment_name = _repo_slug(
                        deployment.repo_url
                    )

                    await db.commit()

                    duration = time.time() - pipeline_start

                    deployments_success.labels(
                        environment=deployment.environment.value
                    ).inc()

                    active_deployments.labels(
                        environment=deployment.environment.value
                    ).dec()

                    deployment_duration.labels(
                        environment=deployment.environment.value,
                        status="success",
                    ).observe(duration)

                    jenkins_build_duration.labels(
                        job_name=settings.JENKINS_JOB_NAME,
                        result="success",
                    ).observe(duration)

                    break

                # ─────────────────────────────────
                # FAILED
                # ─────────────────────────────────

                elif jenkins_status == "failed":

                    deployment.finish(
                        DeploymentStatus.FAILED
                    )

                    await db.commit()

                    duration = time.time() - pipeline_start

                    deployments_failed.labels(
                        environment=deployment.environment.value
                    ).inc()

                    active_deployments.labels(
                        environment=deployment.environment.value
                    ).dec()

                    deployment_duration.labels(
                        environment=deployment.environment.value,
                        status="failed",
                    ).observe(duration)

                    jenkins_build_duration.labels(
                        job_name=settings.JENKINS_JOB_NAME,
                        result="failed",
                    ).observe(duration)

                    break

                # still running
                await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _repo_slug(repo_url: str) -> str:

    parts = repo_url.rstrip("/").split("/")

    return (
        f"{parts[-2]}-{parts[-1]}".lower()
        if len(parts) >= 2
        else "app"
    )