from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.requirement.infrastructure.orm import (
    RequirementAcceptanceCriterionRow,
    RequirementAssessmentEvidenceRefRow,
    RequirementAssumptionRow,
    RequirementCapabilityAssessmentRow,
    RequirementCreateResultRow,
    RequirementDependencyRow,
    RequirementExclusionRow,
    RequirementPackageMembershipRow,
    RequirementPackageCommandResultRow,
    RequirementDecisionEvidenceRefRow,
    RequirementCommandResultRow,
    RequirementPackageCreateResultRow,
    RequirementPackageRow,
    RequirementRow,
    RequirementSourceRow,
    RequirementSourceEvidenceRefRow,
    RequirementStateDecisionRow,
    RequirementVersionRow,
    RequirementVersionAITaskRefRow,
    RequirementVersionCreateResultRow,
    RequirementReviewStateResultRow,
    RequirementRelationRow,
)


class RequirementIdentitySchemaTests(unittest.TestCase):
    def test_identity_and_membership_tables_are_project_scoped(self) -> None:
        tables = (
            RequirementPackageRow.__table__,
            RequirementRow.__table__,
            RequirementPackageMembershipRow.__table__,
        )
        self.assertEqual(
            [table.name for table in tables],
            ["req_packages", "req_requirements", "req_package_memberships"],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual(table.schema, "plm")
                self.assertIn("project_id", table.c)
        self.assertTrue(
            RequirementRow.__table__.c.current_approved_version_ref.nullable
        )
        self.assertEqual(
            [
                RequirementPackageCreateResultRow.__table__.name,
                RequirementCreateResultRow.__table__.name,
                RequirementPackageCommandResultRow.__table__.name,
            ],
            ["req_package_create_results", "req_requirement_create_results",
             "req_package_command_results"],
        )

    def test_same_project_code_and_membership_constraints_exist(self) -> None:
        names = {
            constraint.name
            for table in (
                RequirementPackageRow.__table__,
                RequirementRow.__table__,
                RequirementPackageMembershipRow.__table__,
            )
            for constraint in table.constraints
        }
        for required in (
            "uq_req_packages__id_project",
            "uq_req_requirements__project_code",
            "uq_req_package_memberships__package_requirement",
            "fk_req_package_memberships__package",
            "fk_req_package_memberships__requirement",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_foundation_guard_keeps_owner_and_version_pointer_closed(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0111_requirement_identity_foundation"
        )
        self.assertEqual(migration.down_revision, "20261007_0110")
        for required in (
            "Requirement identity Owner is not installed",
            "RequirementPackage initial state is invalid",
            "Requirement initial state is invalid",
            "NEW.current_approved_version_ref IS NOT NULL",
            "Requirement identity history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0111_requirement_identity_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Requirement identity"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Requirement identity history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )

    def test_create_result_delta_is_immutable_and_history_safe(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0112_requirement_create_results"
        )
        self.assertEqual(migration.down_revision, "20261007_0111")
        for required in (
            "Requirement create result history is immutable",
            "Requirement create result history cannot be truncated",
            "Requirement create result does not match initial identity",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement create"):
                migration.downgrade()
        self.assertIn(
            "Requirement create result history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )

    def test_package_mutation_delta_opens_only_package_and_membership_owner(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0113_requirement_package_mutations"
        )
        self.assertEqual(migration.down_revision, "20261007_0112")
        for required in (
            "RequirementPackage mutation is invalid",
            "Requirement identity Owner is not installed",
            "RequirementPackage membership history cannot be rewritten",
            "RequirementPackage command result history is immutable",
            "RequirementPackage command result does not match current root",
        ):
            self.assertIn(required, migration._MUTATION_GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement Package"):
                migration.downgrade()
        self.assertIn("mutation history prevents downgrade", inspect.getsource(migration.downgrade))

    def test_state_decision_foundation_is_evidence_backed_and_owner_closed(self) -> None:
        self.assertEqual(RequirementStateDecisionRow.__table__.schema, "plm")
        self.assertEqual(RequirementDecisionEvidenceRefRow.__table__.schema, "plm")
        names = {constraint.name for table in (
            RequirementStateDecisionRow.__table__,
            RequirementDecisionEvidenceRefRow.__table__,
        ) for constraint in table.constraints}
        for required in (
            "uq_req_state_decisions__requirement_version",
            "fk_req_state_decisions__requirement",
            "fk_req_decision_evidence_refs__decision",
            "fk_req_decision_evidence_refs__evidence",
        ):
            self.assertIn(required, names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0114_requirement_state_decisions"
        )
        self.assertEqual(migration.down_revision, "20261007_0113")
        self.assertIn("Owner is not installed", migration._GUARDS)
        self.assertIn("history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement state-decision"):
                migration.downgrade()
        self.assertIn("history prevents downgrade", inspect.getsource(migration.downgrade))

    def test_requirement_mutation_owner_has_deferred_database_closure(self) -> None:
        self.assertEqual(RequirementCommandResultRow.__table__.name,
                         "req_requirement_command_results")
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0115_requirement_identity_mutations"
        )
        self.assertEqual(migration.down_revision, "20261007_0114")
        for required in (
            "Requirement identity mutation is invalid",
            "Requirement decision Evidence is not eligible",
            "Requirement mutation has no immutable result",
            "Requirement decision requires Evidence",
            "Requirement command result history is immutable",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement mutation"):
                migration.downgrade()
        self.assertIn("Requirement mutation history prevents downgrade",
                      inspect.getsource(migration.downgrade))

    def test_requirement_version_primary_is_project_scoped_and_owner_closed(self) -> None:
        table = RequirementVersionRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "req_requirement_versions"))
        names = {constraint.name for constraint in table.constraints}
        for required in (
            "uq_req_versions__id_requirement_project",
            "uq_req_versions__requirement_no",
            "fk_req_versions__requirement", "fk_req_versions__supersedes",
            "ck_req_versions__classification", "ck_req_versions__counts",
            "ck_req_versions__supersedes_not_self",
        ):
            self.assertIn(required, names)
        root_names = {constraint.name for constraint in RequirementRow.__table__.constraints}
        self.assertIn("fk_req_requirements__approved_version", root_names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0116_requirement_version_primary")
        self.assertEqual(migration.down_revision, "20261007_0115")
        self.assertIn("RequirementVersion Owner is not installed", migration._GUARDS)
        self.assertIn("history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline RequirementVersion"):
                migration.downgrade()
        self.assertIn("RequirementVersion history prevents downgrade",
                      inspect.getsource(migration.downgrade))

    def test_requirement_version_owned_tables_are_ordered_and_owner_closed(self) -> None:
        tables = (
            RequirementSourceRow.__table__,
            RequirementAcceptanceCriterionRow.__table__,
            RequirementCapabilityAssessmentRow.__table__,
            RequirementAssumptionRow.__table__,
            RequirementExclusionRow.__table__,
            RequirementDependencyRow.__table__,
        )
        self.assertEqual(
            {table.name for table in tables},
            {"req_sources", "req_acceptance_criteria", "req_capability_assessments",
             "req_assumptions", "req_exclusions", "req_dependencies"},
        )
        for table in tables:
            self.assertEqual(table.schema, "plm")
            self.assertIn("ordinal", table.c)
            self.assertTrue(any(
                constraint.name and constraint.name.endswith("__version")
                for constraint in table.constraints
            ), table.name)
            self.assertTrue(any(
                constraint.name and constraint.name.endswith("__version_ordinal")
                for constraint in table.constraints
            ), table.name)
        names = {
            constraint.name
            for constraint in RequirementCapabilityAssessmentRow.__table__.constraints
        }
        self.assertIn("fk_req_assessments__capability", names)
        self.assertIn("ck_req_assessments__assessor_shape", names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0117_requirement_version_owned")
        self.assertEqual(migration.down_revision, "20261007_0116")
        self.assertIn("owned collection Owner is not installed", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline RequirementVersion owned"):
                migration.downgrade()
        self.assertIn("RequirementVersion owned history prevents downgrade",
                      inspect.getsource(migration.downgrade))

    def test_requirement_version_support_refs_close_complete_snapshot(self) -> None:
        tables = (
            RequirementSourceEvidenceRefRow.__table__,
            RequirementAssessmentEvidenceRefRow.__table__,
            RequirementVersionAITaskRefRow.__table__,
        )
        self.assertEqual(
            {table.name for table in tables},
            {"req_source_evidence_refs", "req_assessment_evidence_refs",
             "req_version_ai_task_refs"},
        )
        for table in tables:
            self.assertEqual(table.schema, "plm")
            self.assertIn("requirement_version_id", table.c)
        assessment_names = {
            constraint.name
            for constraint in RequirementAssessmentEvidenceRefRow.__table__.constraints
        }
        self.assertIn("ck_req_assessment_evidence__role", assessment_names)
        ai_names = {
            constraint.name for constraint in RequirementVersionAITaskRefRow.__table__.constraints
        }
        self.assertIn("fk_req_version_ai_refs__task", ai_names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0118_requirement_version_support")
        self.assertEqual(migration.down_revision, "20261007_0117")
        self.assertIn("declared counts do not match", migration._GUARDS)
        self.assertIn("accepted to this draft", migration._GUARDS)
        self.assertIn("pre-existing RequirementVersion", inspect.getsource(migration.upgrade))
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline RequirementVersion support"):
                migration.downgrade()

    def test_requirement_version_create_owner_has_immutable_result_closure(self) -> None:
        table = RequirementVersionCreateResultRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(table.name, "req_requirement_version_create_results")
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("fk_req_version_create_results__version", names)
        self.assertIn("uq_req_version_create_results__requirement_lock", names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0119_requirement_version_create_owner")
        self.assertEqual(migration.down_revision, "20261007_0118")
        self.assertIn("RequirementVersion has no immutable create result",
                      migration._OWNER_GUARDS)
        self.assertIn("Requirement mutation has no immutable result",
                      migration._OWNER_GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline RequirementVersion owner"):
                migration.downgrade()

    def test_requirement_review_lifecycle_has_immutable_root_closure(self) -> None:
        table = RequirementReviewStateResultRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(table.name, "req_requirement_review_state_results")
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("fk_req_review_results__version", names)
        self.assertIn("uq_req_review_results__requirement_lock", names)
        self.assertIn("ck_req_review_results__pointer", names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0120_requirement_review_lifecycle")
        self.assertEqual(migration.down_revision, "20261007_0119")
        self.assertIn("RequirementVersion Review transition has no immutable result",
                      migration._GUARDS)
        self.assertIn("REQUIREMENT_ALL_V1", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement Review"):
                migration.downgrade()

    def test_requirement_relation_schema_is_fixed_version_and_irreversible(self) -> None:
        table = RequirementRelationRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "req_relations"))
        names = {constraint.name for constraint in table.constraints}
        for required in (
            "uq_req_relations__id_project",
            "fk_req_relations__source_version",
            "fk_req_relations__target_version",
            "fk_req_relations__replacement",
            "ck_req_relations__symmetric_order",
            "ck_req_relations__state",
        ):
            self.assertIn(required, names)
        self.assertEqual(
            {index.name for index in table.indexes},
            {"uq_req_relations__active_edge", "ix_req_relations__out",
             "ix_req_relations__in"},
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0121_requirement_relations")
        self.assertEqual(migration.down_revision, "20261007_0120")
        self.assertIn("RequirementRelation lifecycle mutation is invalid",
                      migration._GUARDS)
        self.assertIn("history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline RequirementRelation"):
                migration.downgrade()


if __name__ == "__main__":
    unittest.main()
