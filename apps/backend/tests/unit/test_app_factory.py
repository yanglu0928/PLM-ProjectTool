from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import APP_TITLE, create_app


class AppFactoryTests(unittest.TestCase):
    def test_factory_creates_isolated_instances(self) -> None:
        first = create_app()
        second = create_app()

        self.assertIsNot(first, second)
        self.assertIsNot(first.state.health_service, second.state.health_service)

    def test_factory_uses_safe_defaults(self) -> None:
        app = create_app()

        self.assertEqual(APP_TITLE, app.title)
        self.assertFalse(app.debug)
        self.assertIsNone(app.docs_url)
        self.assertIsNone(app.redoc_url)
        self.assertIsNone(app.openapi_url)

    def test_optional_plugin_installation_read_router_is_mounted_only_when_supplied(self) -> None:
        from fastapi import APIRouter

        router = APIRouter()

        @router.get("/api/v1/admin/plugins/installations/{installation_id}")
        def get_installation(installation_id: str):
            return {"data": {"plugin_installation_id": installation_id}}

        path = "/api/v1/admin/plugins/installations/inst-test"
        app = create_app(plugin_installation_metadata_router=router)
        response = TestClient(app).get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"data": {"plugin_installation_id": "inst-test"}},
        )

        default = create_app()
        response = TestClient(default).get(path)
        self.assertEqual(response.status_code, 404)

    def test_health_service_fails_closed_before_startup(self) -> None:
        app = create_app()

        self.assertFalse(app.state.health_service.started)


if __name__ == "__main__":
    unittest.main()
