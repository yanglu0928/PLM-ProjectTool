from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from plm_assistant.entrypoints.windows_project_review import (
    ProductionProjectReviewStartupError,
    create_windows_project_review_list_router,
    create_windows_project_review_read_router,
    create_windows_project_review_router,
)
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectReadRegistry,
)
from plm_assistant.modules.solution.application.outline_review_subject import (
    OutlineReviewSubjectOwner,
)


class WindowsProjectReviewCompositionTests(unittest.TestCase):
    def test_explicit_outline_subject_registered_for_read_list_and_commands(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        outline = OutlineReviewSubjectOwner(
            repository=Mock(), reviewers=Mock(), readiness=Mock(), audit=Mock())
        owner = Mock(SUBJECT_TYPE="SOL-06")
        owner.authorize_read = Mock()
        section = Mock(SUBJECT_TYPE="SOL-05")
        section.authorize_read = Mock()
        module = "plm_assistant.entrypoints.windows_project_review."
        with (patch(module + "create_windows_structured_spec_review_subject",
                    return_value=owner),
              patch(module + "create_windows_section_review_subject",
                    return_value=section),
              patch(module + "ProjectReviewSubjectReadRegistry",
                    wraps=ProjectReviewSubjectReadRegistry) as reads):
            create_windows_project_review_read_router(
                runtime, origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                outline_subject=outline)
            self.assertEqual((owner, section, outline), reads.call_args.args[0])
            create_windows_project_review_list_router(
                runtime, origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                cursors=Mock(), outline_subject=outline)
            self.assertEqual((owner, section, outline), reads.call_args.args[0])
        with patch(module + "ProjectReviewSubjectRegistry",
                   side_effect=lambda owners: Mock(
                       registered_subject_types=tuple(
                           item.SUBJECT_TYPE for item in owners))) as writes:
            create_windows_project_review_router(
                runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(), documents=Mock(), downloads=Mock(),
                parse_results=Mock(), outline_subject=outline)
        self.assertIs(writes.call_args.args[0][-1], outline)
        self.assertEqual(writes.call_args.args[0][-1].SUBJECT_TYPE, "SOL-03")

    def test_outline_registration_requires_exact_owner_and_complete_sources(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionProjectReviewStartupError):
            create_windows_project_review_router(
                runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(), outline_subject=Mock(SUBJECT_TYPE="SOL-03"))
        with self.assertRaises(ProductionProjectReviewStartupError):
            create_windows_project_review_read_router(
                runtime, origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                outline_subject=Mock(SUBJECT_TYPE="SOL-03"))

    def test_composes_sol06_list_router_with_separate_registry_and_cursor(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        owner = Mock(SUBJECT_TYPE="SOL-06")
        owner.authorize_read = Mock()
        section = Mock(SUBJECT_TYPE="SOL-05")
        section.authorize_read = Mock()
        cursor = Mock()
        with patch(
            "plm_assistant.entrypoints.windows_project_review."
            "create_windows_structured_spec_review_subject",
            return_value=owner,
        ), patch(
            "plm_assistant.entrypoints.windows_project_review."
            "create_windows_section_review_subject", return_value=section,
        ), patch(
            "plm_assistant.entrypoints.windows_project_review."
            "ProjectReviewSubjectReadRegistry",
            wraps=ProjectReviewSubjectReadRegistry,
        ) as registry:
            router = create_windows_project_review_list_router(
                runtime, origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                cursors=cursor,
            )
        self.assertEqual([
            "/api/v1/projects/{project_id}/reviews",
        ], [route.path for route in router.routes])
        self.assertEqual((owner, section), registry.call_args.args[0])

    def test_composes_sol06_read_router_with_separate_registry(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        owner = Mock(SUBJECT_TYPE="SOL-06")
        owner.authorize_read = Mock()
        section = Mock(SUBJECT_TYPE="SOL-05")
        section.authorize_read = Mock()
        with patch(
            "plm_assistant.entrypoints.windows_project_review."
            "create_windows_structured_spec_review_subject",
            return_value=owner,
        ), patch(
            "plm_assistant.entrypoints.windows_project_review."
            "create_windows_section_review_subject", return_value=section,
        ), patch(
            "plm_assistant.entrypoints.windows_project_review."
            "ProjectReviewSubjectReadRegistry",
            wraps=ProjectReviewSubjectReadRegistry,
        ) as registry:
            router = create_windows_project_review_read_router(
                runtime, origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock())
        self.assertEqual([
            "/api/v1/projects/{project_id}/reviews/{review_id}",
        ], [route.path for route in router.routes])
        self.assertEqual((owner, section), registry.call_args.args[0])

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

    def test_registers_requirement_and_prototype_with_unified_project_review(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with patch(
            "plm_assistant.entrypoints.windows_project_review."
            "ProjectReviewSubjectRegistry",
            side_effect=lambda owners: Mock(
                registered_subject_types=tuple(
                    owner.SUBJECT_TYPE for owner in owners
                )
            ),
        ) as registry:
            create_windows_project_review_router(
                runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(),
            )
        owners = registry.call_args.args[0]
        self.assertEqual(
            ("HND-02", "SRV-02", "REQ-03", "PRT-03"),
            tuple(owner.SUBJECT_TYPE for owner in owners),
        )

    def test_missing_dependency_fails_closed_without_raw_cause(self):
        with self.assertRaises(ProductionProjectReviewStartupError) as caught:
            create_windows_project_review_router(
                None, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(),
            )
        self.assertNotIn("None", str(caught.exception))
        with self.assertRaises(ProductionProjectReviewStartupError):
            create_windows_project_review_read_router(
                Mock(), origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=None, parse_results=Mock())
        with self.assertRaises(ProductionProjectReviewStartupError):
            create_windows_project_review_list_router(
                Mock(), origins=Mock(), license_guard=Mock(), audit=Mock(),
                documents=Mock(), downloads=Mock(), parse_results=Mock(),
                cursors=None,
            )

    def test_conclusion_owner_requires_complete_evidence_dependencies(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionProjectReviewStartupError):
            create_windows_project_review_router(
                runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(), documents=Mock(),
            )
        with patch(
            "plm_assistant.entrypoints.windows_project_review."
            "ProjectReviewSubjectRegistry",
            side_effect=lambda owners: Mock(
                registered_subject_types=tuple(
                    owner.SUBJECT_TYPE for owner in owners
                )
            ),
        ) as registry:
            router = create_windows_project_review_router(
                runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                audit=Mock(), documents=Mock(), downloads=Mock(),
                parse_results=Mock(),
            )
        self.assertEqual(4, len(router.routes))
        self.assertEqual(
            ("HND-02", "SRV-02", "REQ-03", "PRT-03", "SRV-05", "SOL-06", "SOL-05"),
            tuple(owner.SUBJECT_TYPE for owner in registry.call_args.args[0]),
        )


if __name__ == "__main__":
    unittest.main()
