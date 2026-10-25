"""Windows Outline VALIDATE is explicit and uses the bounded real owner graph."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import APIRouter

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_outline_version_validate_router,
)
from plm_assistant.modules.requirement.application.approved_inventory import (
    ApprovedRequirementInventoryService,
)
from plm_assistant.modules.requirement.infrastructure.workflow_qualification_repository import (
    SqlAlchemyRequirementWorkflowQualificationRepository,
)
from plm_assistant.modules.solution.application.prove_outline_coverage import (
    OutlineCoverageProofService,
)
from plm_assistant.modules.solution.application.prove_outline_version_current import (
    OutlineVersionCurrentFactsService,
)
from plm_assistant.modules.solution.application.validate_outline_version import (
    OutlineVersionValidationService,
)
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionCurrentValidator,
)


class WindowsOutlineVersionValidateCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kwargs = {
            "runtime": SimpleNamespace(unit_of_work=lambda: None),
            "sessions": object(), "origins": object(),
            "license_guard": object(), "audit": object(),
            "document_storage_root": self.root,
            "parse_result_storage_root": self.root,
            "documents": object(), "downloads": object(),
            "parse_results": object(),
        }

    def test_full_graph_and_bounded_requirement_scope(self):
        captured = {}

        def capture(*, sessions, origins, validations):
            captured["service"] = validations
            return APIRouter()

        with patch(
            "plm_assistant.entrypoints.windows_solution_outline."
            "create_outline_version_validate_router", side_effect=capture,
        ):
            router = create_windows_outline_version_validate_router(**self.kwargs)
        self.assertIsInstance(router, APIRouter)
        service = captured["service"]
        self.assertIsInstance(service, OutlineVersionValidationService)
        current = service._current
        self.assertIsInstance(current, OutlineVersionCurrentFactsService)
        coverage = current._coverage
        self.assertIsInstance(coverage, OutlineCoverageProofService)
        inventory = coverage._inventory
        self.assertIsInstance(inventory, ApprovedRequirementInventoryService)
        repository = inventory._qualification._repo
        self.assertIsInstance(
            repository, SqlAlchemyRequirementWorkflowQualificationRepository)
        self.assertEqual(500, repository._max_roots)
        self.assertIsInstance(coverage._current, SectionVersionCurrentValidator)

    def test_missing_source_fails_closed(self):
        for name in self.kwargs:
            with self.subTest(name=name):
                kwargs = {**self.kwargs, name: None}
                with self.assertRaises(ProductionSolutionOutlineStartupError):
                    create_windows_outline_version_validate_router(**kwargs)


if __name__ == "__main__":
    unittest.main()
