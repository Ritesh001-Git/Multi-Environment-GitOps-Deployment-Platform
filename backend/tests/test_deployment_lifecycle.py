import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import database
from db.database import Base
from models.deployment import Deployment, DeploymentEnvironment, DeploymentStatus
from services import deployment_service as service
from api.routes.deployments import deployment_websocket


class FakeWebSocket:
    def __init__(self):
        self.messages = []
        self.closed = False

    async def accept(self):
        pass

    async def send_json(self, message):
        self.messages.append(message)

    async def close(self):
        self.closed = True


class DeploymentLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.path}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_patch = patch.object(database, "AsyncSessionLocal", self.sessions)
        self.session_patch.start()

    async def asyncTearDown(self):
        self.session_patch.stop()
        await self.engine.dispose()
        os.unlink(self.path)

    async def _insert(self, status=DeploymentStatus.QUEUED, duration=None, build_url=None):
        deployment = Deployment(
            repo_url="https://github.com/example/app",
            branch="main",
            docker_image="example/app",
            environment=DeploymentEnvironment.LOCAL_K8S,
            status=status,
            triggered_by="api",
            duration_seconds=duration,
            jenkins_build_url=build_url,
        )
        if status in service.TERMINAL_STATUSES:
            deployment.finished_at = datetime.now(timezone.utc)
        async with self.sessions() as session, session.begin():
            session.add(deployment)
        return deployment.id

    async def test_successful_jenkins_build_persists_terminal_fields(self):
        deployment_id = await self._insert()
        with (
            patch.object(service, "_trigger_jenkins_build", AsyncMock(return_value=12)),
            patch.object(
                service,
                "_resolve_build_number",
                AsyncMock(return_value=service.JenkinsExecutable(34, "http://jenkins/job/app/34/")),
            ),
            patch.object(
                service,
                "_poll_jenkins_status",
                AsyncMock(return_value=service.JenkinsBuildState("success", 9.5)),
            ),
        ):
            await service.run_pipeline(deployment_id)

        async with self.sessions() as session:
            deployment = await service.get_deployment(session, deployment_id)
            self.assertEqual(deployment.status, DeploymentStatus.SUCCESS)
            self.assertEqual(deployment.jenkins_build_number, 34)
            self.assertEqual(deployment.docker_tag, "34")
            self.assertEqual(deployment.k8s_deployment_name, service.settings.KUBE_DEPLOYMENT_NAME)
            self.assertIsNotNone(deployment.finished_at)
            self.assertIsNotNone(deployment.duration_seconds)

    async def test_pipeline_exception_marks_deployment_failed(self):
        deployment_id = await self._insert()
        with patch.object(
            service, "_trigger_jenkins_build", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            await service.run_pipeline(deployment_id)

        async with self.sessions() as session:
            deployment = await service.get_deployment(session, deployment_id)
            self.assertEqual(deployment.status, DeploymentStatus.FAILED)
            self.assertIsNotNone(deployment.finished_at)
            self.assertIsNotNone(deployment.duration_seconds)

    async def test_recovery_resumes_persisted_queue_without_duplicate_trigger(self):
        deployment_id = await self._insert(
            DeploymentStatus.RUNNING,
            build_url="http://jenkins/queue/item/77/",
        )
        trigger = AsyncMock()
        with (
            patch.object(service, "_trigger_jenkins_build", trigger),
            patch.object(
                service,
                "_resolve_build_number",
                AsyncMock(return_value=service.JenkinsExecutable(35, "http://jenkins/job/app/35/")),
            ),
            patch.object(
                service,
                "_poll_jenkins_status",
                AsyncMock(return_value=service.JenkinsBuildState("success", 8)),
            ),
        ):
            await service.run_pipeline(deployment_id)

        trigger.assert_not_awaited()
        async with self.sessions() as session:
            deployment = await service.get_deployment(session, deployment_id)
            self.assertEqual(deployment.status, DeploymentStatus.SUCCESS)
            self.assertEqual(deployment.jenkins_build_number, 35)

    async def test_stats_use_completed_deployments_for_success_rate(self):
        await self._insert(DeploymentStatus.SUCCESS, 10)
        await self._insert(DeploymentStatus.FAILED, 20)
        await self._insert(DeploymentStatus.RUNNING)
        await self._insert(DeploymentStatus.QUEUED)
        with (
            patch.object(service.k8s_service, "get_running_pod_count", return_value=3),
            patch.object(service.k8s_service, "get_active_service_count", return_value=2),
        ):
            async with self.sessions() as session:
                stats = await service.get_dashboard_stats(session)

        self.assertEqual(stats.total_deployments, 4)
        self.assertEqual(stats.running_deployments, 1)
        self.assertEqual(stats.success_rate, 50.0)
        self.assertEqual(stats.avg_duration_seconds, 15.0)
        self.assertEqual(stats.running_pods, 3)
        self.assertTrue(stats.kubernetes_available)

    async def test_websocket_sends_terminal_state_and_closes(self):
        deployment_id = await self._insert(DeploymentStatus.SUCCESS, 12)
        websocket = FakeWebSocket()
        await deployment_websocket(websocket, deployment_id)
        self.assertEqual(len(websocket.messages), 1)
        self.assertEqual(websocket.messages[0]["status"], "success")
        self.assertEqual(websocket.messages[0]["duration_seconds"], 12)
        self.assertTrue(websocket.closed)


if __name__ == "__main__":
    unittest.main()
