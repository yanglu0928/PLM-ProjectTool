from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError, create_windows_outline_create_router,
    create_windows_outline_version_create_router,
    create_windows_outline_list_router,
    create_windows_outline_read_router,
    create_windows_section_version_read_router,
    create_windows_structured_spec_revise_router,
    create_windows_structured_spec_list_router,
)
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec
from plm_assistant.modules.solution.api.structured_spec_list_cursor import StructuredSpecListCursorCodec


class WindowsSolutionOutlineTests(unittest.TestCase):
    def test_structured_spec_revise_requires_all_write_and_source_trust(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), audit=Mock(), documents=Mock(),
            downloads=Mock(), parse_results=Mock(),
        )
        router = create_windows_structured_spec_revise_router(**dependencies)
        self.assertEqual(
            [("POST", "/api/v1/projects/{project_id}/structured-solution-specs/"
              "{spec_id}:revise")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_structured_spec_revise_router(
                    **{**dependencies, key: None})

    def test_structured_spec_list_requires_dedicated_cursor_and_read_trust(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), cursors=StructuredSpecListCursorCodec(b"x" * 32),
        )
        router = create_windows_structured_spec_list_router(**dependencies)
        self.assertEqual(
            {("GET", "/api/v1/projects/{project_id}/structured-solution-specs"),
             ("POST", "/api/v1/projects/{project_id}/structured-solution-specs")},
            {(method, route.path) for route in router.routes for method in route.methods},
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_structured_spec_list_router(
                    **{**dependencies, key: None})
        with self.assertRaises(ProductionSolutionOutlineStartupError):
            create_windows_structured_spec_list_router(
                **{**dependencies, "cursors": Mock()})

    def test_section_version_history_requires_all_read_trust(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), cursors=SectionVersionListCursorCodec(b"v" * 32),
        )
        router = create_windows_section_version_read_router(**dependencies)
        self.assertEqual(
            {("POST", "/api/v1/projects/{project_id}/solution-sections/"
              "{section_id}/versions"),
             ("GET", "/api/v1/projects/{project_id}/solution-sections/"
              "{section_id}/versions"),
             ("GET", "/api/v1/projects/{project_id}/solution-sections/"
              "{section_id}/versions/{section_version_id}")},
            {(method, route.path) for route in router.routes for method in route.methods},
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_section_version_read_router(
                    **{**dependencies, key: None})
        with self.assertRaises(ProductionSolutionOutlineStartupError):
            create_windows_section_version_read_router(
                **{**dependencies, "cursors": Mock()})

    def test_explicit_list_and_missing_dependencies_fail_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(), cursors=OutlineListCursorCodec(b"o" * 32),
        )
        router = create_windows_outline_list_router(**dependencies)
        self.assertEqual(
            {("GET", "/api/v1/projects/{project_id}/solution-outlines"),
             ("POST", "/api/v1/projects/{project_id}/solution-outlines")},
            {(method, route.path) for route in router.routes for method in route.methods},
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_outline_list_router(**{**dependencies, key: None})
        with self.assertRaises(ProductionSolutionOutlineStartupError):
            create_windows_outline_list_router(**{**dependencies, "cursors": Mock()})

    def test_explicit_get_and_missing_dependencies_fail_closed(self):
        dependencies = dict(
            runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
            license_guard=Mock(),
        )
        router = create_windows_outline_read_router(**dependencies)
        self.assertEqual(
            [("GET", "/api/v1/projects/{project_id}/solution-outlines/{outline_id}")],
            [(method, route.path) for route in router.routes for method in route.methods],
        )
        for key in dependencies:
            with self.subTest(key=key), self.assertRaises(
                    ProductionSolutionOutlineStartupError):
                create_windows_outline_read_router(**{**dependencies, key: None})

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

    def test_version_post_requires_write_trust_and_private_storage_root(self):
        with tempfile.TemporaryDirectory(prefix="plm-outline-version-factory-") as root:
            dependencies = dict(
                runtime=Mock(unit_of_work=Mock()), sessions=Mock(), origins=Mock(),
                license_guard=Mock(), audit=Mock(),
                document_storage_root=Path(root),
                parse_result_storage_root=Path(root),
            )
            router = create_windows_outline_version_create_router(**dependencies)
            self.assertEqual(
                [("POST", "/api/v1/projects/{project_id}/solution-outlines/"
                  "{outline_id}/versions")],
                [(method, route.path) for route in router.routes for method in route.methods],
            )
            for key in dependencies:
                with self.subTest(key=key), self.assertRaises(
                        ProductionSolutionOutlineStartupError):
                    create_windows_outline_version_create_router(
                        **{**dependencies, key: None})
            with self.assertRaises(ProductionSolutionOutlineStartupError):
                create_windows_outline_version_create_router(
                    **{**dependencies, "document_storage_root": Path("relative")})
            with self.assertRaises(ProductionSolutionOutlineStartupError):
                create_windows_outline_version_create_router(
                    **{**dependencies, "parse_result_storage_root": Path("relative")})


if __name__ == "__main__":
    unittest.main()
