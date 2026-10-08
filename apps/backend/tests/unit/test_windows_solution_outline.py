from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError, create_windows_outline_create_router,
)


class WindowsSolutionOutlineTests(unittest.TestCase):
    def test_explicit_post_and_missing_dependencies_fail_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), audit=Mock(),
        )
        router = create_windows_outline_create_router(**dependencies)
        self.assertEqual(
            [("POST", "/api/v1/projects/{project_id}/solution-outlines")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_outline_create_router(**{**dependencies, key: None})


if __name__ == "__main__":
    unittest.main()
