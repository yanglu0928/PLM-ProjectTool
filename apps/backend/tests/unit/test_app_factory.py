from __future__ import annotations

import unittest

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

    def test_health_service_fails_closed_before_startup(self) -> None:
        app = create_app()

        self.assertFalse(app.state.health_service.started)


if __name__ == "__main__":
    unittest.main()
