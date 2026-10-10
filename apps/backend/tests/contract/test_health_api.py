from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app


class HealthApiTests(unittest.TestCase):
    def test_liveness_is_minimal_and_not_cached(self) -> None:
        with TestClient(create_app()) as client:
            response = client.get("/health/live")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "UP"}, response.json())
        self.assertEqual("no-store", response.headers["cache-control"])

    def test_readiness_is_up_during_lifespan(self) -> None:
        with TestClient(create_app()) as client:
            response = client.get("/health/ready")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "UP"}, response.json())

    def test_failed_probe_returns_safe_503(self) -> None:
        def failing_probe() -> bool:
            raise RuntimeError("database=secret-host; path=C:/private")

        with TestClient(create_app(readiness_checks=[failing_probe])) as client:
            response = client.get("/health/ready")

        self.assertEqual(503, response.status_code)
        self.assertEqual({"status": "NOT_READY"}, response.json())
        self.assertNotIn("secret-host", response.text)
        self.assertNotIn("private", response.text)

    def test_false_probe_returns_503(self) -> None:
        with TestClient(create_app(readiness_checks=[lambda: False])) as client:
            response = client.get("/health/ready")

        self.assertEqual(503, response.status_code)
        self.assertEqual({"status": "NOT_READY"}, response.json())

    def test_async_probe_is_supported(self) -> None:
        async def healthy_probe() -> bool:
            return True

        with TestClient(create_app(readiness_checks=[healthy_probe])) as client:
            response = client.get("/health/ready")

        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()
