from __future__ import annotations

import unittest

from plm_assistant.modules.platform.infrastructure.orm import (
    APPLICATION_SCHEMA,
    NAMING_CONVENTION,
    Base,
)
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure import idempotency_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure import secret_orm  # noqa: F401
from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import user_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import session_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import login_rate_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import installation_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import validation_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import trusted_time_orm  # noqa: F401
from plm_assistant.modules.project.infrastructure import orm as project_orm  # noqa: F401
from plm_assistant.modules.document.infrastructure import orm as document_orm  # noqa: F401
from plm_assistant.modules.evidence.infrastructure import orm as evidence_orm  # noqa: F401
from plm_assistant.modules.trace.infrastructure import orm as trace_orm  # noqa: F401
from plm_assistant.modules.workflow.infrastructure import orm as workflow_orm  # noqa: F401
from plm_assistant.modules.workflow.infrastructure import history_orm  # noqa: F401
from plm_assistant.modules.workflow.infrastructure import checklist_record_orm  # noqa: F401
from plm_assistant.modules.review.infrastructure import orm as review_orm  # noqa: F401
from plm_assistant.modules.jobs.infrastructure import orm as jobs_orm  # noqa: F401


class OrmMetadataTests(unittest.TestCase):
    def test_application_schema_is_frozen_plm_schema(self) -> None:
        self.assertEqual(APPLICATION_SCHEMA, "plm")
        self.assertEqual(Base.metadata.schema, "plm")

    def test_constraint_naming_convention_is_complete(self) -> None:
        self.assertEqual(
            set(NAMING_CONVENTION),
            {"ix", "uq", "ck", "fk", "pk"},
        )

    def test_platform_audit_auth_and_license_tables_are_registered(self) -> None:
        self.assertIn("plm.trc_links", Base.metadata.tables)
        self.assertEqual(set(Base.metadata.tables) - {"plm.trc_links"} - {"plm."+t.name for t in review_orm._tables}, {"plm.wfl_checklist_records", "plm.wfl_checklist_record_refs", "plm.wfl_stage_transitions", "plm.wfl_transition_gate_items", "plm.wfl_transition_gate_refs", "plm.wfl_project_workflows", "plm.wfl_stages", "plm.wfl_stage_checklists", "plm.wfl_checklist_items", "plm.plt_system_configurations", "plm.plt_configuration_versions", "plm.plt_configuration_command_receipts", "plm.plt_idempotency_receipts", "plm.plt_secret_records", "plm.plt_secret_versions", "plm.aud_events", "plm.auth_users", "plm.auth_password_credentials", "plm.auth_sessions", "plm.auth_login_rate_buckets", "plm.lic_installations", "plm.lic_validation_events", "plm.lic_validation_states", "plm.lic_installation_documents", "plm.lic_trusted_time_events", "plm.lic_trusted_time_states", "plm.prj_projects", "plm.prj_departments", "plm.prj_department_create_results", "plm.prj_department_deactivate_results", "plm.prj_project_members", "plm.prj_member_assignment_history", "plm.prj_member_create_results", "plm.prj_member_state_results", "plm.doc_file_objects", "plm.doc_file_state_events", "plm.doc_documents", "plm.doc_document_versions", "plm.doc_version_source_refs", "plm.doc_upload_intents", "plm.doc_parse_records", "plm.doc_parse_result_refs", "plm.evd_evidence_records", "plm.job_jobs", "plm.job_attempts", "plm.job_leases", "plm.job_outbox_events", "plm.job_outbox_consumptions"})


if __name__ == "__main__":
    unittest.main()
