"""Deployment orchestration, persistence, Jenkins integration, and statistics."""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from k8s.client import k8s_service
from metrics import (
    active_deployments,
    deployment_duration,
    deployments_failed,
    deployments_success,
    deployments_total,
    jenkins_build_duration,
    jenkins_builds_triggered,
)
from models.deployment import Deployment, DeploymentStatus
from schemas.deployment import DashboardStats, DeployRequest

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    DeploymentStatus.SUCCESS,
    DeploymentStatus.FAILED,
    DeploymentStatus.CANCELLED,
}
_pipeline_tasks: dict[str, asyncio.Task[None]] = {}


@dataclass(frozen=True)
class DeploymentSnapshot:
    id: str
    repo_url: str
    branch: str
    docker_image: str
    environment: str
    triggered_by: str
    status: DeploymentStatus
    build_number: Optional[int]
    queue_id: Optional[int]
    started_at: datetime


@dataclass(frozen=True)
class JenkinsBuildState:
    state: str
    duration_seconds: Optional[float] = None
    result: Optional[str] = None


@dataclass(frozen=True)
class JenkinsExecutable:
    number: int
    url: str


class JenkinsIntegrationError(RuntimeError):
    """A Jenkins failure that is safe to persist and show to an operator."""


def _response_body(response: httpx.Response, limit: int = 2000) -> str:
    body = response.text.strip()
    return body[:limit] + ("..." if len(body) > limit else "")


async def _jenkins_crumb(http: httpx.AsyncClient) -> dict[str, str]:
    """Return a CSRF crumb header when Jenkins has the crumb issuer enabled."""
    url = f"{settings.JENKINS_URL.rstrip('/')}/crumbIssuer/api/json"
    try:
        response = await http.get(url, auth=_jenkins_auth())
    except httpx.HTTPError as exc:
        raise JenkinsIntegrationError(f"Jenkins crumb request failed: {exc}") from exc
    logger.info("Jenkins crumb response", extra={"url": url, "status": response.status_code})
    if response.status_code == 404:
        return {}
    if response.status_code in (401, 403):
        raise JenkinsIntegrationError(
            f"Jenkins authentication failed while requesting CSRF crumb (HTTP {response.status_code})"
        )
    if response.status_code != 200:
        raise JenkinsIntegrationError(
            f"Jenkins crumb endpoint returned HTTP {response.status_code}: {_response_body(response)}"
        )
    try:
        data = response.json()
        field, crumb = data["crumbRequestField"], data["crumb"]
    except (ValueError, KeyError, TypeError) as exc:
        raise JenkinsIntegrationError(
            f"Jenkins crumb response was invalid: {_response_body(response)}"
        ) from exc
    return {str(field): str(crumb)}


def _jenkins_auth() -> tuple[str, str]:
    return settings.JENKINS_USER, settings.JENKINS_TOKEN


def _jenkins_job_url() -> str:
    # Jenkins folder jobs are represented as /job/folder/job/name.
    parts = [quote(part, safe="") for part in settings.JENKINS_JOB_NAME.split("/")]
    return f"{settings.JENKINS_URL.rstrip('/')}/job/" + "/job/".join(parts)


async def _trigger_jenkins_build(
    http: httpx.AsyncClient, deployment: DeploymentSnapshot
) -> int:
    url = f"{_jenkins_job_url()}/buildWithParameters"
    parameters = {
        "REPO_URL": deployment.repo_url,
        "BRANCH": deployment.branch,
        "DOCKER_IMAGE": deployment.docker_image,
        "ENVIRONMENT": deployment.environment,
        "APP_EC2_IP": settings.K3S_DEPLOY_HOST,
    }
    logger.info(
        "Triggering Jenkins build",
        extra={"deployment_id": deployment.id, "url": url, "parameters": parameters},
    )
    headers = await _jenkins_crumb(http)
    try:
        response = await http.post(
            url, params=parameters, headers=headers, auth=_jenkins_auth()
        )
    except httpx.HTTPError as exc:
        raise JenkinsIntegrationError(f"Jenkins trigger request failed: {exc}") from exc
    location = response.headers.get("Location") or response.headers.get("location") or ""
    logger.info(
        "Jenkins trigger response",
        extra={
            "deployment_id": deployment.id,
            "status": response.status_code,
            "location": location,
            "body": _response_body(response),
        },
    )
    if response.status_code in (401, 403):
        raise JenkinsIntegrationError(
            f"Jenkins trigger authentication/authorization failed (HTTP {response.status_code}): "
            f"{_response_body(response)}"
        )
    if response.status_code not in (200, 201, 302):
        raise JenkinsIntegrationError(
            f"Jenkins rejected build trigger (HTTP {response.status_code}): {_response_body(response)}"
        )
    queue_url = urljoin(f"{settings.JENKINS_URL.rstrip('/')}/", location)
    match = re.search(r"/queue/item/(\d+)/?", urlparse(queue_url).path)
    queue_id = int(match.group(1)) if match else None
    if queue_id is None:
        raise JenkinsIntegrationError(
            "Jenkins accepted the build but did not return a queue item Location header"
        )
    logger.info(
        "Jenkins queue item assigned",
        extra={"deployment_id": deployment.id, "queue_id": queue_id, "queue_url": queue_url},
    )
    return queue_id


async def _resolve_build_number(
    http: httpx.AsyncClient, queue_item_id: int
) -> JenkinsExecutable:
    url = f"{settings.JENKINS_URL.rstrip('/')}/queue/item/{queue_item_id}/api/json"
    deadline = time.monotonic() + settings.JENKINS_QUEUE_TIMEOUT_SECONDS
    errors = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(min(settings.POLL_INTERVAL_SECONDS, 2))
        try:
            response = await http.get(url, auth=_jenkins_auth())
            logger.info(
                "Jenkins queue poll",
                extra={"queue_id": queue_item_id, "status": response.status_code, "body": _response_body(response)},
            )
            if response.status_code in (401, 403):
                raise JenkinsIntegrationError(
                    f"Jenkins queue authentication/authorization failed (HTTP {response.status_code}): "
                    f"{_response_body(response)}"
                )
            # A freshly-created queue item can briefly return 404 through a
            # proxy. Treat this and other transient HTTP failures as bounded
            # polling errors; the body has already been logged above.
            response.raise_for_status()
            data = response.json()
            if data.get("cancelled"):
                raise JenkinsIntegrationError(f"Jenkins queue item {queue_item_id} was cancelled")
            executable = data.get("executable") or {}
            if executable.get("number") is not None:
                number = int(executable["number"])
                build_url = str(executable.get("url") or f"{_jenkins_job_url()}/{number}/")
                logger.info(
                    "Jenkins build assigned",
                    extra={"queue_id": queue_item_id, "build_number": number, "build_url": build_url},
                )
                return JenkinsExecutable(number, build_url)
            errors = 0
        except JenkinsIntegrationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            errors += 1
            logger.warning(
                "Unable to resolve Jenkins queue item",
                exc_info=True,
                extra={"queue_id": queue_item_id, "attempt_errors": errors},
            )
            if errors >= settings.JENKINS_MAX_POLL_ERRORS:
                raise JenkinsIntegrationError(
                    f"Jenkins queue polling failed {errors} consecutive times: {exc}"
                ) from exc
    raise JenkinsIntegrationError(
        f"Timed out after {settings.JENKINS_QUEUE_TIMEOUT_SECONDS}s waiting for Jenkins queue item {queue_item_id}"
    )


async def _poll_jenkins_status(
    http: httpx.AsyncClient, build_number: int
) -> JenkinsBuildState:
    url = f"{_jenkins_job_url()}/{build_number}/api/json"
    response = await http.get(url, auth=_jenkins_auth())
    if response.status_code != 200:
        raise JenkinsIntegrationError(
            f"Jenkins build API returned HTTP {response.status_code}: {_response_body(response)}"
        )
    data = response.json()
    duration = data.get("duration")
    duration_seconds = float(duration) / 1000 if duration is not None else None
    if data.get("building") or data.get("result") is None:
        return JenkinsBuildState("running", duration_seconds)
    result = str(data.get("result")).upper()
    logger.info("Jenkins build status", extra={"build_number": build_number, "result": result})
    if result == "SUCCESS":
        return JenkinsBuildState("success", duration_seconds, result)
    if result in {"FAILURE", "ABORTED", "NOT_BUILT", "UNSTABLE"}:
        return JenkinsBuildState("failed", duration_seconds, result)
    raise JenkinsIntegrationError(f"Jenkins returned unknown build result {result!r}")


async def create_deployment(db: AsyncSession, payload: DeployRequest) -> Deployment:
    repo_parts = payload.repo_url.rstrip("/").removesuffix(".git").split("/")
    image_name = payload.docker_image or (
        f"{settings.DOCKERHUB_USER}/{repo_parts[-2]}-{repo_parts[-1]}".lower()
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


async def get_deployment(db: AsyncSession, deployment_id: str) -> Optional[Deployment]:
    result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
    return result.scalar_one_or_none()


async def list_deployments(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status: Optional[DeploymentStatus] = None,
) -> tuple[int, list[Deployment]]:
    filters = [Deployment.status == status] if status else []
    total = (
        await db.execute(select(func.count(Deployment.id)).where(*filters))
    ).scalar_one()
    items = (
        await db.execute(
            select(Deployment)
            .where(*filters)
            .order_by(desc(Deployment.started_at), desc(Deployment.id))
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return total, list(items)


async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    rows = (
        await db.execute(
            select(Deployment.status, func.count(Deployment.id)).group_by(Deployment.status)
        )
    ).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    successful = counts.get(DeploymentStatus.SUCCESS, 0)
    failed = counts.get(DeploymentStatus.FAILED, 0)
    running = counts.get(DeploymentStatus.RUNNING, 0)
    completed = successful + failed
    avg_duration = (
        await db.execute(
            select(func.avg(Deployment.duration_seconds)).where(
                Deployment.status.in_([DeploymentStatus.SUCCESS, DeploymentStatus.FAILED]),
                Deployment.duration_seconds.is_not(None),
            )
        )
    ).scalar_one_or_none()

    # The Kubernetes SDK is synchronous; never block FastAPI's event loop.
    k8s_results = await asyncio.gather(
        asyncio.to_thread(k8s_service.get_running_pod_count, settings.KUBE_NAMESPACE),
        asyncio.to_thread(k8s_service.get_active_service_count, settings.KUBE_NAMESPACE),
        return_exceptions=True,
    )
    k8s_error = next((result for result in k8s_results if isinstance(result, BaseException)), None)
    if k8s_error:
        logger.error("Kubernetes dashboard query failed: %s", k8s_error)
    running_pods = None if isinstance(k8s_results[0], BaseException) else k8s_results[0]
    active_services = None if isinstance(k8s_results[1], BaseException) else k8s_results[1]
    return DashboardStats(
        total_deployments=total,
        successful_deployments=successful,
        failed_deployments=failed,
        running_deployments=running,
        success_rate=round(successful / completed * 100, 1) if completed else 0.0,
        running_pods=running_pods,
        active_services=active_services,
        kubernetes_available=k8s_error is None,
        kubernetes_error=type(k8s_error).__name__ if k8s_error else None,
        avg_duration_seconds=round(float(avg_duration), 1) if avg_duration is not None else None,
    )


async def _load_snapshot(deployment_id: str) -> Optional[DeploymentSnapshot]:
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        deployment = await get_deployment(db, deployment_id)
        if deployment is None:
            return None
        queue_match = re.search(
            r"/queue/item/(\d+)/?", deployment.jenkins_build_url or ""
        )
        return DeploymentSnapshot(
            id=deployment.id,
            repo_url=deployment.repo_url,
            branch=deployment.branch,
            docker_image=deployment.docker_image or "",
            environment=deployment.environment.value,
            triggered_by=deployment.triggered_by,
            status=deployment.status,
            build_number=deployment.jenkins_build_number,
            queue_id=int(queue_match.group(1)) if queue_match else None,
            started_at=deployment.started_at,
        )


async def _mark_running(deployment_id: str) -> None:
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db, db.begin():
        deployment = await get_deployment(db, deployment_id)
        if deployment and deployment.status == DeploymentStatus.QUEUED:
            deployment.status = DeploymentStatus.RUNNING


async def _store_build_number(deployment_id: str, executable: JenkinsExecutable) -> None:
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db, db.begin():
        deployment = await get_deployment(db, deployment_id)
        if deployment and deployment.status not in TERMINAL_STATUSES:
            deployment.jenkins_build_number = executable.number
            deployment.jenkins_build_url = executable.url
            deployment.docker_tag = str(executable.number)


async def _store_queue_id(deployment_id: str, queue_id: int) -> None:
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db, db.begin():
        deployment = await get_deployment(db, deployment_id)
        if deployment and deployment.status not in TERMINAL_STATUSES:
            deployment.jenkins_build_url = (
                f"{settings.JENKINS_URL.rstrip('/')}/queue/item/{queue_id}/"
            )


async def _finish_deployment(deployment_id: str, status: DeploymentStatus) -> bool:
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db, db.begin():
        deployment = await get_deployment(db, deployment_id)
        if deployment is None or deployment.status in TERMINAL_STATUSES:
            return False
        deployment.finish(status)
        if status == DeploymentStatus.SUCCESS:
            deployment.k8s_deployment_name = settings.KUBE_DEPLOYMENT_NAME
        return True


async def run_pipeline(deployment_id: str) -> None:
    """Run or resume one deployment without retaining ORM objects across I/O."""
    snapshot = await _load_snapshot(deployment_id)
    if snapshot is None:
        logger.error("Deployment does not exist", extra={"deployment_id": deployment_id})
        return
    if snapshot.status in TERMINAL_STATUSES:
        return

    metric_started = False
    pipeline_start = time.monotonic()
    final_status: Optional[DeploymentStatus] = None
    reported_duration: Optional[float] = None
    try:
        deployments_total.labels(
            environment=snapshot.environment, triggered_by=snapshot.triggered_by
        ).inc()
        active_deployments.labels(environment=snapshot.environment).inc()
        metric_started = True
        await _mark_running(deployment_id)

        timeout = httpx.Timeout(settings.JENKINS_REQUEST_TIMEOUT_SECONDS)
        # A Jenkins 302 trigger response carries the queue URL in Location. Never
        # follow it: doing so loses the header required to resolve the build.
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
            build_number = snapshot.build_number
            if build_number is None:
                queue_id = snapshot.queue_id
                if queue_id is None:
                    queue_id = await _trigger_jenkins_build(http, snapshot)
                    await _store_queue_id(deployment_id, queue_id)
                    jenkins_builds_triggered.labels(job_name=settings.JENKINS_JOB_NAME).inc()
                executable = await _resolve_build_number(http, queue_id)
                build_number = executable.number
                await _store_build_number(deployment_id, executable)

            deadline = time.monotonic() + settings.JENKINS_BUILD_TIMEOUT_SECONDS
            consecutive_errors = 0
            while time.monotonic() < deadline:
                try:
                    state = await _poll_jenkins_status(http, build_number)
                    consecutive_errors = 0
                except (httpx.HTTPError, ValueError, TypeError, JenkinsIntegrationError):
                    consecutive_errors += 1
                    logger.warning(
                        "Jenkins build status poll failed",
                        exc_info=True,
                        extra={
                            "deployment_id": deployment_id,
                            "build_number": build_number,
                            "consecutive_errors": consecutive_errors,
                        },
                    )
                    if consecutive_errors >= settings.JENKINS_MAX_POLL_ERRORS:
                        final_status = DeploymentStatus.FAILED
                        return
                    await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
                    continue

                reported_duration = state.duration_seconds
                if state.state == "success":
                    final_status = DeploymentStatus.SUCCESS
                    return
                if state.state == "failed":
                    final_status = DeploymentStatus.FAILED
                    return
                await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

            logger.error(
                "Jenkins build status timed out",
                extra={"deployment_id": deployment_id, "build_number": build_number},
            )
            final_status = DeploymentStatus.FAILED
    except asyncio.CancelledError:
        logger.info("Pipeline task cancelled during shutdown", extra={"deployment_id": deployment_id})
        raise
    except Exception:
        logger.exception("Deployment pipeline crashed", extra={"deployment_id": deployment_id})
        final_status = DeploymentStatus.FAILED
    finally:
        if final_status is not None:
            changed = await _finish_deployment(deployment_id, final_status)
            duration = time.monotonic() - pipeline_start
            if changed:
                metric = deployments_success if final_status == DeploymentStatus.SUCCESS else deployments_failed
                metric.labels(environment=snapshot.environment).inc()
                result = final_status.value
                deployment_duration.labels(
                    environment=snapshot.environment, status=result
                ).observe(duration)
                jenkins_build_duration.labels(
                    job_name=settings.JENKINS_JOB_NAME, result=result
                ).observe(reported_duration if reported_duration is not None else duration)
                logger.info(
                    "Deployment reached terminal state",
                    extra={"deployment_id": deployment_id, "status": result},
                )
        if metric_started:
            active_deployments.labels(environment=snapshot.environment).dec()


async def prepare_pipeline(deployment_id: str) -> int:
    """Synchronously obtain a Jenkins queue item, then let polling run in background.

    Keeping this small first step in the API request means authentication, job-name,
    CSRF, and parameter failures are returned to the frontend instead of becoming an
    opaque FAILED record a fraction of a second later.
    """
    snapshot = await _load_snapshot(deployment_id)
    if snapshot is None:
        raise JenkinsIntegrationError(f"Deployment {deployment_id} does not exist")
    await _mark_running(deployment_id)
    timeout = httpx.Timeout(settings.JENKINS_REQUEST_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
            queue_id = await _trigger_jenkins_build(http, snapshot)
        await _store_queue_id(deployment_id, queue_id)
        jenkins_builds_triggered.labels(job_name=settings.JENKINS_JOB_NAME).inc()
        return queue_id
    except Exception:
        await _finish_deployment(deployment_id, DeploymentStatus.FAILED)
        raise


def start_pipeline(deployment_id: str) -> asyncio.Task[None]:
    """Start one strongly-referenced task and prevent duplicates in this process."""
    current = _pipeline_tasks.get(deployment_id)
    if current and not current.done():
        return current
    task = asyncio.create_task(run_pipeline(deployment_id), name=f"deployment-{deployment_id}")
    _pipeline_tasks[deployment_id] = task
    def remove_completed(done: asyncio.Task[None]) -> None:
        if _pipeline_tasks.get(deployment_id) is done:
            _pipeline_tasks.pop(deployment_id, None)

    task.add_done_callback(remove_completed)
    return task


async def resume_incomplete_pipelines() -> int:
    """Resume queued/running records after a process restart."""
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        ids = (
            await db.execute(
                select(Deployment.id).where(
                    Deployment.status.in_([DeploymentStatus.QUEUED, DeploymentStatus.RUNNING])
                )
            )
        ).scalars().all()
    for deployment_id in ids:
        start_pipeline(deployment_id)
    return len(ids)


async def stop_pipeline_tasks() -> None:
    tasks = [task for task in _pipeline_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
