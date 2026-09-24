from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app


class LifespanIntegrationTests(unittest.TestCase):
    def test_lifespan_marks_service_started_then_stopped(self) -> None:
        app = create_app()
        service = app.state.health_service

        self.assertFalse(service.started)
        with TestClient(app):
            self.assertTrue(service.started)
        self.assertFalse(service.started)

    def test_sequential_app_instances_do_not_share_lifecycle_state(self) -> None:
        first = create_app()
        second = create_app()

        with TestClient(first):
            self.assertTrue(first.state.health_service.started)
            self.assertFalse(second.state.health_service.started)


if __name__ == "__main__":
    unittest.main()
