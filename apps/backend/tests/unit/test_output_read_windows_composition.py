from __future__ import annotations

import unittest
from unittest.mock import Mock

from fastapi import APIRouter, FastAPI

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output_read import (
    ProductionOutputReadStartupError,
    create_windows_output_request_read_router,
)


class OutputReadCompositionTests(unittest.TestCase):
    def test_factory_wires_request_and_artifact_routes(self):
        runtime = Mock()
        sessions, origins, guard, session_access = object(), object(), object(), object()
        router = create_windows_output_request_read_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, session_access=session_access,
        )
        self.assertIsInstance(router, APIRouter)
        composed = FastAPI()
        composed.include_router(router)
        paths = {getattr(item, "path", None) for item in composed.routes}
        self.assertIn(
            "/api/v1/projects/{project_id}/output-requests/{output_request_id}", paths,
        )
        self.assertIn(
            "/api/v1/projects/{project_id}/output-requests/{output_request_id}/artifact",
            paths,
        )

    def test_missing_runtime_dependency_fails_closed(self):
        with self.assertRaises(ProductionOutputReadStartupError):
            create_windows_output_request_read_router(
                runtime=None, sessions=object(), origins=object(),
                license_guard=object(),
            )

    def test_read_route_is_opt_in(self):
        path = "/api/v1/projects/{project_id}/output-requests/{output_request_id}"
        self.assertNotIn(path, create_app().openapi().get("paths", {}))
        router = APIRouter()
        router.add_api_route(path, lambda: None, methods=["GET"])
        app: FastAPI = create_app(output_request_read_router=router)
        self.assertIn("get", app.openapi().get("paths", {}).get(path, {}))


if __name__ == "__main__":
    unittest.main()
