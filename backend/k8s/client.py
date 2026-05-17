"""
k8s/client.py — Kubernetes Python client wrapper.
Handles both in-cluster (pod) and kubeconfig (local/EC2) modes.
All methods return plain dicts / Pydantic models — no k8s objects leak out.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed

from core.config import settings
from schemas.deployment import PodOut, K8sDeploymentOut, K8sOverview

logger = logging.getLogger(__name__)


def _get_k8s_clients():
    """
    Lazy-load the kubernetes client.
    Returns (CoreV1Api, AppsV1Api) or raises if k8s is not reachable.
    """
    try:
        from kubernetes import client, config as k8s_config
        if settings.KUBE_MODE == "in-cluster":
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config()
        return client.CoreV1Api(), client.AppsV1Api()
    except Exception as e:
        logger.warning(f"Kubernetes not available: {e}")
        raise


def _parse_image(image: str) -> tuple[str, str]:
    """Split 'repo/name:tag' → ('repo/name', 'tag')."""
    if ":" in image:
        parts = image.rsplit(":", 1)
        return parts[0], parts[1]
    return image, "latest"


def _age_seconds(timestamp: Optional[datetime]) -> int:
    if timestamp is None:
        return 0
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - timestamp).total_seconds())


def _pod_ready(pod) -> bool:
    if not pod.status.conditions:
        return False
    for cond in pod.status.conditions:
        if cond.type == "Ready":
            return cond.status == "True"
    return False


def _pod_restart_count(pod) -> int:
    if not pod.status.container_statuses:
        return 0
    return sum(cs.restart_count for cs in pod.status.container_statuses)


def _pod_to_schema(pod) -> PodOut:
    image = ""
    if pod.spec.containers:
        image = pod.spec.containers[0].image or ""
    img_name, img_tag = _parse_image(image)

    return PodOut(
        name=pod.metadata.name,
        namespace=pod.metadata.namespace,
        status=pod.status.phase or "Unknown",
        ready=_pod_ready(pod),
        restart_count=_pod_restart_count(pod),
        node_name=pod.spec.node_name,
        image=img_name,
        image_tag=img_tag,
        age_seconds=_age_seconds(pod.metadata.creation_timestamp),
        labels=pod.metadata.labels or {},
    )


def _deployment_to_schema(dep) -> K8sDeploymentOut:
    image = ""
    if dep.spec.template.spec.containers:
        image = dep.spec.template.spec.containers[0].image or ""

    return K8sDeploymentOut(
        name=dep.metadata.name,
        namespace=dep.metadata.namespace,
        desired_replicas=dep.spec.replicas or 0,
        ready_replicas=dep.status.ready_replicas or 0,
        available_replicas=dep.status.available_replicas or 0,
        image=image,
        created_at=dep.metadata.creation_timestamp,
    )


class KubernetesService:
    """
    Wraps kubernetes-client calls.
    Every public method catches exceptions and returns safe defaults
    so the API never 500s just because k8s is unreachable.
    """

    def get_pods(self, namespace: str = "default") -> list[PodOut]:
        try:
            core, _ = _get_k8s_clients()
            if namespace == "all":
                pods = core.list_pod_for_all_namespaces(watch=False)
            else:
                pods = core.list_namespaced_pod(namespace=namespace, watch=False)
            return [_pod_to_schema(p) for p in pods.items]
        except Exception as e:
            logger.error(f"get_pods failed: {e}")
            return []

    def get_deployments(self, namespace: str = "default") -> list[K8sDeploymentOut]:
        try:
            _, apps = _get_k8s_clients()
            if namespace == "all":
                deps = apps.list_deployment_for_all_namespaces(watch=False)
            else:
                deps = apps.list_namespaced_deployment(namespace=namespace, watch=False)
            return [_deployment_to_schema(d) for d in deps.items]
        except Exception as e:
            logger.error(f"get_deployments failed: {e}")
            return []

    def get_namespaces(self) -> list[str]:
        try:
            core, _ = _get_k8s_clients()
            ns_list = core.list_namespace(watch=False)
            return [n.metadata.name for n in ns_list.items]
        except Exception as e:
            logger.error(f"get_namespaces failed: {e}")
            return ["default"]

    def get_overview(self, namespace: str = "default") -> K8sOverview:
        pods = self.get_pods(namespace)
        deployments = self.get_deployments(namespace)
        namespaces = self.get_namespaces()

        return K8sOverview(
            pods=pods,
            deployments=deployments,
            namespaces=namespaces,
            total_pods=len(pods),
            running_pods=sum(1 for p in pods if p.status == "Running"),
            pending_pods=sum(1 for p in pods if p.status == "Pending"),
            failed_pods=sum(1 for p in pods if p.status == "Failed"),
        )

    def get_running_pod_count(self, namespace: str = "default") -> int:
        pods = self.get_pods(namespace)
        return sum(1 for p in pods if p.status == "Running")

    def get_active_service_count(self, namespace: str = "default") -> int:
        try:
            core, _ = _get_k8s_clients()
            if namespace == "all":
                svcs = core.list_service_for_all_namespaces(watch=False)
            else:
                svcs = core.list_namespaced_service(namespace=namespace, watch=False)
            # Exclude kubernetes default service
            return sum(1 for s in svcs.items if s.metadata.name != "kubernetes")
        except Exception as e:
            logger.error(f"get_active_service_count failed: {e}")
            return 0


# Singleton — import this everywhere
k8s_service = KubernetesService()