from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app


class PublicSurfaceTests(unittest.TestCase):
    def test_only_minimal_health_routes_are_registered(self) -> None:
        app = create_app()
        paths = set(app.openapi()["paths"])

        self.assertEqual({"/health/live", "/health/ready"}, paths)

    def test_docs_openapi_root_and_business_prefix_are_not_exposed(self) -> None:
        with TestClient(create_app()) as client:
            for path in ("/", "/docs", "/redoc", "/openapi.json", "/api/v1"):
                with self.subTest(path=path):
                    self.assertEqual(404, client.get(path).status_code)


if __name__ == "__main__":
    unittest.main()
