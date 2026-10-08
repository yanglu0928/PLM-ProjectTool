from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_solution_reference import (
    ProductionSolutionReferenceStartupError,
    create_windows_global_reference_create_router,
    create_windows_project_reference_create_router,
    create_windows_project_reference_list_router,
    create_windows_project_reference_read_router,
    create_windows_reference_deidentification_router,
)
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


class WindowsSolutionReferenceTests(unittest.TestCase):
    def test_project_list_and_missing_dependency_fails_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), cursors=ReferenceListCursorCodec(b"r" * 32),
        )
        router = create_windows_project_reference_list_router(**dependencies)
        self.assertEqual(
            [("POST", "/api/v1/projects/{project_id}/reference-solutions"),
             ("GET", "/api/v1/projects/{project_id}/reference-solutions")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionReferenceStartupError):
                create_windows_project_reference_list_router(
                    **{**dependencies, key: None})

    def test_project_get_and_missing_dependency_fails_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(),
        )
        router = create_windows_project_reference_read_router(**dependencies)
        self.assertEqual(
            [("GET", "/api/v1/projects/{project_id}/reference-solutions/"
              "{reference_solution_id}")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionReferenceStartupError):
                create_windows_project_reference_read_router(
                    **{**dependencies, key: None})

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

    def test_only_global_post_and_missing_dependency_fails_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), audit=Mock(), documents=Mock(),
            downloads=Mock(), parse_results=Mock(),
        )
        router = create_windows_global_reference_create_router(**dependencies)
        self.assertEqual(
            [("POST", "/api/v1/global/reference-solutions")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionReferenceStartupError):
                create_windows_global_reference_create_router(
                    **{**dependencies, key: None})

    def test_global_attestation_only_explicit_write_composition(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), audit=Mock(), documents=Mock(),
            downloads=Mock(), parse_results=Mock(),
        )
        router = create_windows_reference_deidentification_router(**dependencies)
        self.assertEqual(
            {("POST", "/api/v1/global/reference-deidentification-confirmations:preview"),
             ("POST", "/api/v1/global/reference-deidentification-confirmations"),
             ("POST", "/api/v1/global/reference-deidentification-confirmations:lookup-operation"),
             ("POST", "/api/v1/global/reference-deidentification-confirmations/"
                      "{confirmation_id}:revoke")},
            {(method, route.path) for route in router.routes for method in route.methods})
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionReferenceStartupError):
                create_windows_reference_deidentification_router(
                    **{**dependencies, key: None})


if __name__ == "__main__":
    unittest.main()
