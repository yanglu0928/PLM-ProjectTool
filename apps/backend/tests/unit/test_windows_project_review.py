from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_project_review import (
    ProductionProjectReviewStartupError,
    create_windows_project_review_router,
)


class WindowsProjectReviewCompositionTests(unittest.TestCase):
    def test_composes_one_set_of_four_review_write_routes(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        router = create_windows_project_review_router(
            runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
            audit=Mock(),
        )
        self.assertEqual([
            "/api/v1/projects/{project_id}/reviews",
            "/api/v1/projects/{project_id}/reviews/{review_id}/rounds",
            "/api/v1/projects/{project_id}/reviews/{review_id}/rounds/"
            "{review_round_id}:decide",
            "/api/v1/projects/{project_id}/reviews/{review_id}/rounds/"
            "{review_round_id}:withdraw",
        ], [route.path for route in router.routes])

    def test_missing_dependency_fails_closed_without_raw_cause(self):
        with self.assertRaises(ProductionProjectReviewStartupError) as caught:
            create_windows_project_review_router(
                None, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(),
            )
        self.assertNotIn("None", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
