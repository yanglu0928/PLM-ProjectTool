from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_workflow_checklist import (
    ProductionWorkflowChecklistStartupError,
    _create_qualification_registry,
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.requirement.application.workflow_qualification import (
    RequirementWorkflowQualificationOwner,
)
from plm_assistant.modules.prototype.application.workflow_qualification import (
    PrototypeWorkflowQualificationOwner,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService


class WindowsWorkflowChecklistCompositionTests(unittest.TestCase):
    def test_prototype_owner_requires_explicit_physical_storage_and_is_shared(self):
        storage = Mock()
        registry = _create_qualification_registry(
            documents=Mock(), downloads=Mock(), parse_results=Mock(),
            artifact_storage=storage,
        )
        prototype = registry._owners["PROTOTYPE_COVERAGE"]
        self.assertIsInstance(prototype, PrototypeWorkflowQualificationOwner)
        self.assertIs(
            prototype, registry._owners["PROTOTYPE_SCOPE_DECISIONS"],
        )
        self.assertIs(
            prototype._req_owner, registry._owners["REQUIREMENT_ACCEPTANCE"],
        )
        self.assertIs(prototype._integrity._storage, storage)
        with self.assertRaises(ProductionWorkflowChecklistStartupError):
            _create_qualification_registry(
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                artifact_storage=object(),
            )

    def test_registry_includes_requirement_aggregate_owner(self):
        registry = _create_qualification_registry(
            documents=Mock(), downloads=Mock(), parse_results=Mock(),
        )

        self.assertEqual((
            "HANDOVER_BASELINE", "HANDOVER_ISSUES",
            "REQUIREMENT_ACCEPTANCE", "REQUIREMENT_FORMAL_VERSIONS",
            "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION",
        ), registry.item_keys)
        self.assertIsInstance(
            registry._owners["REQUIREMENT_FORMAL_VERSIONS"],
            RequirementWorkflowQualificationOwner,
        )
        self.assertIs(
            registry._owners["REQUIREMENT_FORMAL_VERSIONS"],
            registry._owners["REQUIREMENT_ACCEPTANCE"],
        )

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

    def test_composes_qualification_preview_with_real_owner_graph(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        router = create_windows_workflow_checklist_qualification_router(
            runtime,
            sessions=Mock(), origins=Mock(), license_guard=Mock(),
            documents=Mock(), downloads=Mock(), parse_results=Mock(),
        )

        self.assertEqual([
            "/api/v1/projects/{project_id}/workflow/checklist-items/"
            "{item_key}/qualification",
        ], [route.path for route in router.routes])

    def test_qualification_preview_missing_dependency_fails_closed(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionWorkflowChecklistStartupError):
            create_windows_workflow_checklist_qualification_router(
                runtime,
                sessions=Mock(), origins=Mock(), license_guard=Mock(),
                documents=Mock(), downloads=None, parse_results=Mock(),
            )

    def test_composes_transition_with_real_owner_graph(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        router = create_windows_workflow_stage_transition_router(
            runtime,
            sessions=Mock(), origins=Mock(), license_guard=Mock(), audit=Mock(),
            documents=Mock(), downloads=Mock(), parse_results=Mock(),
        )

        self.assertEqual([
            "/api/v1/projects/{project_id}/workflow:transition",
        ], [route.path for route in router.routes])

    def test_transition_missing_dependency_fails_closed(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionWorkflowChecklistStartupError):
            create_windows_workflow_stage_transition_router(
                runtime,
                sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(), documents=Mock(), downloads=Mock(),
                parse_results=None,
            )


if __name__ == "__main__":
    unittest.main()
