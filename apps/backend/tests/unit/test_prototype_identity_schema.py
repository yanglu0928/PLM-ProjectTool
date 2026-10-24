from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.prototype.infrastructure.orm import (
    PrototypeCreateResultRow,
    PrototypeCommandResultRow,
    PrototypePackageMembershipRow,
    PrototypePackageCommandResultRow,
    PrototypePackageCreateResultRow,
    PrototypePackageRow,
    PrototypeRow,
    PrototypeScopeDecisionRequirementRefRow,
    PrototypeScopeDecisionResultRow,
    PrototypeScopeDecisionRow,
    PrototypeTemplateArtifactRefRow,
    PrototypeTemplateCommandResultRow,
    PrototypeTemplateRow,
    PrototypeTemplateVersionRow,
    PrototypeInteractionSpecRow,
    PrototypeVersionArtifactRefRow,
    PrototypeVersionRequirementRefRow,
    PrototypeVersionCreateResultRow,
    PrototypeVersionApprovalTraceManifestRow,
    PrototypeVersionApprovalTraceSourceRow,
    PrototypeVersionReviewStateResultRow,
    PrototypeVersionRow,
    RequirementPrototypeLinkRow,
)


class PrototypeIdentitySchemaTests(unittest.TestCase):
    def test_identity_and_membership_are_project_scoped(self) -> None:
        tables = (
            PrototypePackageRow.__table__,
            PrototypeRow.__table__,
            PrototypePackageMembershipRow.__table__,
        )
        self.assertEqual(
            [table.name for table in tables],
            ["prt_packages", "prt_prototypes", "prt_package_memberships"],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual(table.schema, "plm")
                self.assertIn("project_id", table.c)
        self.assertTrue(PrototypeRow.__table__.c.current_approved_version_ref.nullable)

    def test_cross_project_membership_is_closed_by_composite_foreign_keys(self) -> None:
        names = {
            constraint.name
            for table in (
                PrototypePackageRow.__table__,
                PrototypeRow.__table__,
                PrototypePackageMembershipRow.__table__,
            )
            for constraint in table.constraints
        }
        for required in (
            "uq_prt_packages__id_project",
            "uq_prt_prototypes__id_project",
            "uq_prt_package_memberships__package_prototype",
            "fk_prt_package_memberships__package",
            "fk_prt_package_memberships__prototype",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_not_required_decision_fixes_requirement_versions(self) -> None:
        decision = PrototypeScopeDecisionRow.__table__
        refs = PrototypeScopeDecisionRequirementRefRow.__table__
        self.assertEqual((decision.schema, decision.name), ("plm", "prt_scope_decisions"))
        self.assertEqual(
            (refs.schema, refs.name),
            ("plm", "prt_scope_decision_requirement_refs"),
        )
        names = {
            constraint.name
            for table in (decision, refs)
            for constraint in table.constraints
        }
        for required in (
            "uq_prt_scope_decisions__prototype",
            "fk_prt_scope_decisions__prototype",
            "ck_prt_scope_decisions__review_pair",
            "uq_prt_scope_req_refs__decision_version",
            "uq_prt_scope_req_refs__decision_ordinal",
            "fk_prt_scope_req_refs__decision",
            "fk_prt_scope_req_refs__requirement_version",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_foundation_keeps_decision_owner_and_version_pointer_closed(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0122_prototype_identity_scope"
        )
        self.assertEqual(migration.down_revision, "20261007_0121")
        for required in (
            "Prototype scope decision Owner is not installed",
            "Prototype identity Owner is not installed",
            "PrototypePackage initial state is invalid",
            "Prototype initial state is invalid",
            "NEW.current_approved_version_ref IS NOT NULL",
            "Prototype identity and scope history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0122_prototype_identity_scope"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Prototype identity"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Prototype identity or scope history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )

    def test_create_results_close_identity_and_are_history_safe(self) -> None:
        self.assertEqual(
            [PrototypePackageCreateResultRow.__table__.name,
             PrototypeCreateResultRow.__table__.name],
            ["prt_package_create_results", "prt_prototype_create_results"],
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0123_prototype_create_results"
        )
        self.assertEqual(migration.down_revision, "20261008_0122")
        for required in (
            "Prototype create result history is immutable",
            "PrototypePackage has no immutable create result",
            "Prototype has no immutable create result",
            "pre-existing Prototype identity requires audited migration",
        ):
            self.assertIn(required, migration._GUARDS + inspect.getsource(migration.upgrade))
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Prototype create-result"):
                migration.downgrade()

    def test_package_mutation_result_closes_root_and_membership(self) -> None:
        self.assertEqual(
            PrototypePackageCommandResultRow.__table__.name,
            "prt_package_command_results",
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0124_prototype_package_mutations"
        )
        self.assertEqual(migration.down_revision, "20261008_0123")
        for required in (
            "PrototypePackage mutation is invalid",
            "PrototypePackage membership history cannot be rewritten",
            "PrototypePackage command result history is immutable",
            "PrototypePackage mutation has no immutable result",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PrototypePackage mutation"):
                migration.downgrade()

    def test_prototype_mutation_result_closes_identity(self) -> None:
        self.assertEqual(
            PrototypeCommandResultRow.__table__.name,
            "prt_prototype_command_results",
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0125_prototype_identity_mutations"
        )
        self.assertEqual(migration.down_revision, "20261008_0124")
        for required in (
            "Prototype identity mutation is invalid",
            "Prototype command result history is immutable",
            "Prototype mutation has no immutable result",
            "current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Prototype mutation"):
                migration.downgrade()

    def test_scope_decision_result_closes_not_required_transition(self) -> None:
        self.assertEqual(
            PrototypeScopeDecisionResultRow.__table__.name,
            "prt_scope_decision_results",
        )
        self.assertIn(
            "decision_fingerprint", PrototypeScopeDecisionRow.__table__.c,
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0126_prototype_scope_decisions"
        )
        self.assertEqual(migration.down_revision, "20261008_0125")
        for required in (
            "Prototype scope decision history is immutable",
            "Prototype scope decision RequirementVersion is not current Approved",
            "Prototype scope decision has no complete immutable result",
            "Prototype mutation has no immutable result",
            "PRT_SCOPE_DECISION",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Prototype scope-decision"):
                migration.downgrade()

    def test_template_foundation_is_scoped_versioned_and_owner_closed(self) -> None:
        tables = (
            PrototypeTemplateRow.__table__,
            PrototypeTemplateVersionRow.__table__,
            PrototypeTemplateArtifactRefRow.__table__,
            PrototypeTemplateCommandResultRow.__table__,
        )
        self.assertEqual(
            [table.name for table in tables],
            ["prt_templates", "prt_template_versions",
             "prt_template_artifact_refs", "prt_template_command_results"],
        )
        for table in tables:
            self.assertEqual(table.schema, "plm")
            self.assertIn("scope", table.c)
            self.assertIn("project_id", table.c)
        names = {
            constraint.name for table in tables for constraint in table.constraints
        }
        for required in (
            "fk_prt_templates__current_version",
            "uq_prt_template_versions__template_no",
            "fk_prt_template_versions__supersedes",
            "uq_prt_template_artifact_refs__version_ordinal",
            "uq_prt_template_artifact_refs__version_target",
            "fk_prt_template_artifact_refs__version",
            "fk_prt_template_command_results__version",
        ):
            self.assertIn(required, names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0127_prototype_template_foundation"
        )
        self.assertEqual(migration.down_revision, "20261008_0126")
        self.assertIn("PrototypeTemplate Owner is not installed", migration._GUARDS)
        self.assertIn("PrototypeTemplate history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PrototypeTemplate"):
                migration.downgrade()

    def test_template_create_owner_closes_root_version_artifacts_and_result(self) -> None:
        self.assertIn(
            "declared_artifact_count", PrototypeTemplateVersionRow.__table__.c,
        )
        self.assertIn(
            "declared_artifact_count", PrototypeTemplateCommandResultRow.__table__.c,
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0128_prototype_template_create"
        )
        self.assertEqual(migration.down_revision, "20261008_0127")
        for required in (
            "PrototypeTemplate initial state is invalid",
            "PrototypeTemplate first version is invalid",
            "PrototypeTemplate ArtifactRef set is incomplete",
            "PrototypeTemplate has no immutable create result",
            "pre-existing PrototypeTemplate requires audited migration",
        ):
            self.assertIn(required, migration._GUARDS + inspect.getsource(migration.upgrade))
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(
                RuntimeError, "offline PrototypeTemplate create-owner"
            ):
                migration.downgrade()

    def test_template_revise_owner_closes_chain_pointer_artifacts_and_result(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0129_prototype_template_revise"
        )
        self.assertEqual(migration.down_revision, "20261008_0128")
        for required in (
            "PrototypeTemplate revision update is invalid",
            "PrototypeTemplate revision version is invalid",
            "PrototypeTemplate prior version is inconsistent",
            "PrototypeTemplate revision ArtifactRef set is incomplete",
            "PrototypeTemplate has no immutable revise result",
            "WHERE operation='REVISE'",
        ):
            self.assertIn(
                required,
                migration._GUARDS + inspect.getsource(migration.downgrade),
            )
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(
                RuntimeError, "offline PrototypeTemplate revise-owner"
            ):
                migration.downgrade()

    def test_prototype_version_foundation_is_closed_and_project_scoped(self) -> None:
        tables = (
            PrototypeVersionRow.__table__,
            PrototypeVersionArtifactRefRow.__table__,
            PrototypeVersionRequirementRefRow.__table__,
            PrototypeInteractionSpecRow.__table__,
        )
        self.assertEqual(
            tuple(table.name for table in tables),
            ("prt_prototype_versions", "prt_version_artifact_refs",
             "prt_version_requirement_refs", "prt_interaction_specs"),
        )
        self.assertTrue(all(table.schema == "plm" for table in tables))
        names = {
            constraint.name for table in tables for constraint in table.constraints
        }
        for required in (
            "uq_prt_versions__id_prototype_project",
            "fk_prt_versions__supersedes",
            "fk_prt_versions__template_version",
            "fk_prt_version_artifacts__version",
            "fk_prt_version_requirements__requirement",
            "uq_prt_interactions__version",
        ):
            self.assertIn(required, names)
        root_names = {
            constraint.name for constraint in PrototypeRow.__table__.constraints
        }
        self.assertIn("fk_prt_prototypes__approved_version", root_names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0130_prototype_version_foundation"
        )
        self.assertEqual(migration.down_revision, "20261008_0129")
        self.assertIn("PrototypeVersion Owner is not installed", migration._GUARDS)
        self.assertIn("PrototypeVersion history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PrototypeVersion"):
                migration.downgrade()

    def test_prototype_version_create_owner_closes_chain_sets_and_result(self) -> None:
        self.assertEqual(
            PrototypeVersionCreateResultRow.__table__.name,
            "prt_version_create_results",
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0131_prototype_version_create"
        )
        self.assertEqual(migration.down_revision, "20261008_0130")
        source = migration._OPEN_GUARDS + inspect.getsource(migration.upgrade)
        for required in (
            "PrototypeVersion chain is invalid",
            "PrototypeVersion create set is incomplete",
            "guard_prototype_version_create_result",
            "prt_version_create_results",
            "pre-existing PrototypeVersion requires audited migration",
        ):
            self.assertIn(required, source)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(
                RuntimeError, "offline PrototypeVersion create-owner"
            ):
                migration.downgrade()

    def test_prototype_review_lifecycle_schema_is_a_narrow_owner(self) -> None:
        table = PrototypeVersionReviewStateResultRow.__table__
        self.assertEqual(table.name, "prt_version_review_state_results")
        names = {constraint.name for constraint in table.constraints}
        for required in (
            "uq_prt_review_results__prototype_lock",
            "uq_prt_review_results__version_event",
            "fk_prt_review_results__version",
            "ck_prt_review_results__pointer",
        ):
            self.assertIn(required, names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0132_prototype_review_lifecycle"
        )
        self.assertEqual(migration.down_revision, "20261008_0131")
        source = migration._VERSION_GUARD + migration._ROOT_GUARD + migration._REVIEW_GUARDS
        for required in (
            "PrototypeVersion cannot be created during Review",
            "PROTOTYPE_ALL_V1", "Prototype previous approval was not superseded",
            "PrototypeVersion Review transition has no immutable result",
            "Prototype approval pointer has no immutable result",
        ):
            self.assertIn(required, source)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Prototype Review"):
                migration.downgrade()

    def test_prototype_approval_trace_manifest_is_immutable_and_exact(self) -> None:
        manifest = PrototypeVersionApprovalTraceManifestRow.__table__
        source_table = PrototypeVersionApprovalTraceSourceRow.__table__
        self.assertEqual(manifest.name, "prt_version_approval_trace_manifests")
        self.assertEqual(source_table.name, "prt_version_approval_trace_sources")
        names = {
            constraint.name
            for table in (manifest, source_table)
            for constraint in table.constraints
        }
        for required in (
            "uq_prt_approval_manifests__version",
            "uq_prt_approval_manifests__review_result",
            "fk_prt_approval_sources__manifest",
            "fk_prt_approval_sources__trace_link",
            "ck_prt_approval_sources__shape",
        ):
            self.assertIn(required, names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0133_prototype_approval_trace_manifest"
        )
        self.assertEqual(migration.down_revision, "20261008_0132")
        for required in (
            "Prototype approval Trace manifest source set is incomplete",
            "Prototype approval has no Trace manifest",
            "Prototype approval Trace document source set is not exact",
            "Prototype approval Trace requirement source set is not exact",
            "l.target_owner_module='prototype'",
            "l.target_object_type='PRT-03'",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(
                RuntimeError, "offline Prototype approval Trace"
            ):
                migration.downgrade()

    def test_requirement_prototype_link_is_fixed_scoped_and_irreversible(self) -> None:
        table = RequirementPrototypeLinkRow.__table__
        self.assertEqual(table.name, "prt_requirement_links")
        self.assertEqual(table.schema, "plm")
        names = {constraint.name for constraint in table.constraints}
        for required in (
            "uq_prt_requirement_links__id_project",
            "fk_prt_requirement_links__requirement_version",
            "fk_prt_requirement_links__prototype_version",
            "fk_prt_requirement_links__replacement",
            "ck_prt_requirement_links__purpose",
            "ck_prt_requirement_links__coverage",
            "ck_prt_requirement_links__state",
        ):
            self.assertIn(required, names)
        indexes = {index.name for index in table.indexes}
        self.assertIn(
            "uq_prt_requirement_links__active_identity_purpose", indexes
        )
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261008_0134_requirement_prototype_links"
        )
        self.assertEqual(migration.down_revision, "20261008_0133")
        for required in (
            "RequirementPrototypeLink history is immutable",
            "RequirementPrototypeLink lifecycle mutation is invalid",
            "RequirementPrototypeLink replacement is invalid",
            "RequirementPrototypeLink history cannot be truncated",
            "DEFERRABLE INITIALLY DEFERRED",
        ):
            self.assertIn(
                required,
                migration._GUARDS + inspect.getsource(migration.upgrade),
            )
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(
                RuntimeError, "offline RequirementPrototypeLink"
            ):
                migration.downgrade()


if __name__ == "__main__":
    unittest.main()
