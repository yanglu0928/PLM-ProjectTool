from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_solution_reference import (
    ProductionSolutionReferenceStartupError,
    create_windows_project_reference_create_router,
)


class WindowsSolutionReferenceTests(unittest.TestCase):
    def test_only_project_post_and_missing_dependency_fails_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), audit=Mock(), documents=Mock(),
            downloads=Mock(), parse_results=Mock(),
        )
        router = create_windows_project_reference_create_router(**dependencies)
        self.assertEqual(
            [("POST", "/api/v1/projects/{project_id}/reference-solutions")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionReferenceStartupError):
                create_windows_project_reference_create_router(
                    **{**dependencies, key: None})


if __name__ == "__main__":
    unittest.main()
