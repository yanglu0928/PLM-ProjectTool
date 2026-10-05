from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_workflow_checklist import (
    ProductionWorkflowChecklistStartupError,
    create_windows_workflow_checklist_record_router,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService


class WindowsWorkflowChecklistCompositionTests(unittest.TestCase):
    def test_composes_frozen_record_route_with_explicit_owner_registry(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        router = create_windows_workflow_checklist_record_router(
            runtime,
            sessions=Mock(), origins=Mock(), license_guard=Mock(), audit=Mock(),
            documents=Mock(), downloads=Mock(), parse_results=Mock(),
            target_proofs=TraceTargetProofService({}),
        )

        self.assertEqual([
            "/api/v1/projects/{project_id}/workflow/checklist-items/"
            "{item_key}:record",
        ], [route.path for route in router.routes])

    def test_missing_dependency_fails_closed(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionWorkflowChecklistStartupError):
            create_windows_workflow_checklist_record_router(
                runtime,
                sessions=Mock(), origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=None, downloads=Mock(), parse_results=Mock(),
            )


if __name__ == "__main__":
    unittest.main()
