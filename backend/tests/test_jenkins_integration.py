import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.deployment import DeploymentStatus
from services import deployment_service as service


def snapshot() -> service.DeploymentSnapshot:
    return service.DeploymentSnapshot(
        id="deployment-1",
        repo_url="https://github.com/example/app",
        branch="main",
        docker_image="example/app",
        environment="local-k8s",
        triggered_by="api",
        status=DeploymentStatus.QUEUED,
        build_number=None,
        queue_id=None,
        started_at=datetime.now(timezone.utc),
    )


class JenkinsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def client(self, handler):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)

    async def test_trigger_success_accepts_302_and_exact_parameters(self):
        seen = {}

        def handler(request):
            if request.url.path == "/crumbIssuer/api/json":
                return httpx.Response(404, request=request)
            seen.update(dict(request.url.params))
            return httpx.Response(
                302, headers={"Location": "/queue/item/42/"}, request=request
            )

        async with self.client(handler) as client:
            queue_id = await service._trigger_jenkins_build(client, snapshot())
        self.assertEqual(queue_id, 42)
        self.assertEqual(
            seen,
            {
                "REPO_URL": "https://github.com/example/app",
                "BRANCH": "main",
                "DOCKER_IMAGE": "example/app",
                "ENVIRONMENT": "local-k8s",
                "APP_EC2_IP": service.settings.K3S_DEPLOY_HOST,
            },
        )

    async def test_trigger_sends_csrf_crumb(self):
        def handler(request):
            if request.url.path == "/crumbIssuer/api/json":
                return httpx.Response(
                    200,
                    json={"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"},
                    request=request,
                )
            self.assertEqual(request.headers["Jenkins-Crumb"], "abc")
            return httpx.Response(201, headers={"Location": "/queue/item/7/"}, request=request)

        async with self.client(handler) as client:
            self.assertEqual(await service._trigger_jenkins_build(client, snapshot()), 7)

    async def test_authentication_failure_is_explicit(self):
        def handler(request):
            return httpx.Response(401, text="bad credentials", request=request)

        async with self.client(handler) as client:
            with self.assertRaisesRegex(service.JenkinsIntegrationError, "authentication"):
                await service._trigger_jenkins_build(client, snapshot())

    async def test_invalid_job_is_explicit(self):
        def handler(request):
            if request.url.path == "/crumbIssuer/api/json":
                return httpx.Response(404, request=request)
            return httpx.Response(404, text="No such job", request=request)

        async with self.client(handler) as client:
            with self.assertRaisesRegex(service.JenkinsIntegrationError, "HTTP 404.*No such job"):
                await service._trigger_jenkins_build(client, snapshot())

    async def test_queue_timeout(self):
        def handler(request):
            return httpx.Response(200, json={"why": "waiting"}, request=request)

        with patch.object(service.settings, "JENKINS_QUEUE_TIMEOUT_SECONDS", 0):
            async with self.client(handler) as client:
                with self.assertRaisesRegex(service.JenkinsIntegrationError, "Timed out"):
                    await service._resolve_build_number(client, 1)

    async def test_queue_cancellation(self):
        def handler(request):
            return httpx.Response(200, json={"cancelled": True}, request=request)

        with patch.object(service.asyncio, "sleep", return_value=None):
            async with self.client(handler) as client:
                with self.assertRaisesRegex(service.JenkinsIntegrationError, "cancelled"):
                    await service._resolve_build_number(client, 2)

    async def test_build_number_and_url_resolution(self):
        def handler(request):
            return httpx.Response(
                200,
                json={"executable": {"number": 99, "url": "http://jenkins/job/app/99/"}},
                request=request,
            )

        with patch.object(service.asyncio, "sleep", return_value=None):
            async with self.client(handler) as client:
                executable = await service._resolve_build_number(client, 3)
        self.assertEqual(executable.number, 99)
        self.assertEqual(executable.url, "http://jenkins/job/app/99/")

    async def test_polling_success(self):
        def handler(request):
            return httpx.Response(
                200, json={"building": False, "result": "SUCCESS", "duration": 2500}, request=request
            )

        async with self.client(handler) as client:
            state = await service._poll_jenkins_status(client, 9)
        self.assertEqual(state.state, "success")
        self.assertEqual(state.duration_seconds, 2.5)

    async def test_polling_failure_variants(self):
        for result in ("FAILURE", "ABORTED", "NOT_BUILT"):
            def handler(request, result=result):
                return httpx.Response(
                    200, json={"building": False, "result": result, "duration": 1000}, request=request
                )

            async with self.client(handler) as client:
                state = await service._poll_jenkins_status(client, 10)
            self.assertEqual(state.state, "failed")
            self.assertEqual(state.result, result)


if __name__ == "__main__":
    unittest.main()
