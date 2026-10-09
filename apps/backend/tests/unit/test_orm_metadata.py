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
from plm_assistant.modules.audit.infrastructure import export_orm  # noqa: F401
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
from plm_assistant.modules.platform.infrastructure import maintenance_orm  # noqa: F401
from plm_assistant.modules.ai.infrastructure import provider_orm  # noqa: F401
from plm_assistant.modules.ai.infrastructure import model_orm  # noqa: F401
from plm_assistant.modules.ai.infrastructure import prompt_orm  # noqa: F401
from plm_assistant.modules.ai.infrastructure import task_orm  # noqa: F401
from plm_assistant.modules.ai.infrastructure import egress_orm  # noqa: F401
from plm_assistant.modules.rag.infrastructure import orm as rag_orm  # noqa: F401
from plm_assistant.modules.capability.infrastructure import orm as capability_orm  # noqa: F401
from plm_assistant.modules.handover.infrastructure import orm as handover_orm  # noqa: F401
from plm_assistant.modules.survey.infrastructure import orm as survey_orm  # noqa: F401
from plm_assistant.modules.requirement.infrastructure import orm as requirement_orm  # noqa: F401
from plm_assistant.modules.prototype.infrastructure import orm as prototype_orm  # noqa: F401
from plm_assistant.modules.solution.infrastructure import orm as solution_orm  # noqa: F401


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
        self.assertIn('plm.auth_user_create_results', Base.metadata.tables)
        self.assertIn('plm.auth_user_state_results', Base.metadata.tables)
        self.assertIn('plm.auth_password_change_results', Base.metadata.tables)
        self.assertIn('plm.auth_password_reset_results', Base.metadata.tables)
        # Keep the historical inventory assertion independent of the new Auth history.
        historical_metadata = set(Base.metadata.tables) - {'plm.auth_user_create_results','plm.auth_user_state_results','plm.auth_password_change_results','plm.auth_password_reset_results', 'plm.job_parse_cancel_versions', 'plm.plt_maintenance_state', 'plm.ai_providers', 'plm.ai_provider_config_versions', 'plm.ai_provider_probe_results', 'plm.ai_provider_activation_results', 'plm.ai_models', 'plm.ai_model_capabilities', 'plm.ai_quality_profile_refs', 'plm.ai_model_state_results', 'plm.ai_prompt_templates', 'plm.ai_prompt_versions', 'plm.ai_prompt_version_create_results', 'plm.ai_prompt_activation_results', 'plm.ai_prompt_retire_results', 'plm.ai_tasks', 'plm.ai_task_input_refs', 'plm.ai_egress_authorization_snapshots', 'plm.ai_task_retry_generations', 'plm.ai_invocations', 'plm.ai_invocation_context_refs', 'plm.ai_egress_previews', 'plm.ai_egress_preview_source_refs', 'plm.ai_egress_authorizations', 'plm.ai_egress_authorization_revocations', 'plm.ai_egress_authorize_results', 'plm.ai_egress_revoke_results', 'plm.ai_execution_content_plans', 'plm.ai_execution_content_sources', 'plm.ai_suggestion_payloads', 'plm.ai_suggestion_evidence_refs', 'plm.rag_document_chunks', 'plm.rag_embedding_indexes', 'plm.rag_index_source_chunks', 'plm.rag_embedding_records', 'plm.rag_embedding_builds', 'plm.rag_embedding_build_batches', 'plm.rag_embedding_index_validations', 'plm.rag_embedding_index_quality_results', 'plm.rag_embedding_index_activation_results', 'plm.rag_retrieval_runs', 'plm.rag_retrieval_query_contents', 'plm.rag_retrieval_candidates', 'plm.rag_retrieval_score_parts', 'plm.rag_context_bundles', 'plm.rag_context_items', 'plm.cap_baselines', 'plm.cap_baseline_versions', 'plm.cap_items', 'plm.cap_item_document_refs', 'plm.cap_item_evidence_refs', 'plm.hnd_analyses', 'plm.hnd_analysis_versions', 'plm.hnd_analysis_source_document_refs', 'plm.hnd_analysis_ai_task_refs', 'plm.hnd_analysis_items', 'plm.hnd_item_evidence_refs', 'plm.hnd_item_capability_refs', 'plm.hnd_item_options', 'plm.hnd_action_items', 'plm.hnd_action_response_refs', 'plm.hnd_action_evidence_refs', 'plm.hnd_action_state_events', 'plm.srv_surveys', 'plm.srv_survey_versions', 'plm.srv_questions', 'plm.srv_question_options', 'plm.srv_question_source_refs', 'plm.srv_target_departments', 'plm.srv_rounds', 'plm.srv_round_source_records', 'plm.srv_assignments', 'plm.srv_responses', 'plm.srv_answers', 'plm.srv_answer_evidence_refs', 'plm.srv_conclusions', 'plm.srv_department_conclusions', 'plm.srv_module_conclusions', 'plm.srv_conclusion_evidence_refs', 'plm.srv_conclusion_open_issues', 'plm.req_packages', 'plm.req_requirements', 'plm.req_package_memberships', 'plm.req_package_create_results', 'plm.req_requirement_create_results'}
        historical_metadata.discard('plm.req_package_command_results')
        historical_metadata.discard('plm.req_requirement_state_decisions')
        historical_metadata.discard('plm.req_requirement_decision_evidence_refs')
        historical_metadata.discard('plm.req_requirement_command_results')
        historical_metadata.discard('plm.req_requirement_versions')
        historical_metadata.discard('plm.req_sources')
        historical_metadata.discard('plm.req_acceptance_criteria')
        historical_metadata.discard('plm.req_capability_assessments')
        historical_metadata.discard('plm.req_assumptions')
        historical_metadata.discard('plm.req_exclusions')
        historical_metadata.discard('plm.req_dependencies')
        historical_metadata.discard('plm.req_source_evidence_refs')
        historical_metadata.discard('plm.req_assessment_evidence_refs')
        historical_metadata.discard('plm.req_version_ai_task_refs')
        historical_metadata.discard('plm.req_requirement_version_create_results')
        historical_metadata.discard('plm.req_requirement_review_state_results')
        historical_metadata.discard('plm.req_relations')
        self.assertIn('plm.ai_providers', Base.metadata.tables)
        self.assertIn('plm.ai_provider_config_versions', Base.metadata.tables)
        self.assertIn('plm.ai_provider_probe_results', Base.metadata.tables)
        self.assertIn('plm.ai_provider_activation_results', Base.metadata.tables)
        self.assertIn('plm.ai_models', Base.metadata.tables)
        self.assertIn('plm.ai_model_capabilities', Base.metadata.tables)
        self.assertIn('plm.ai_quality_profile_refs', Base.metadata.tables)
        self.assertIn('plm.ai_model_state_results', Base.metadata.tables)
        self.assertIn('plm.ai_prompt_templates', Base.metadata.tables)
        self.assertIn('plm.ai_prompt_versions', Base.metadata.tables)
        self.assertIn('plm.ai_prompt_version_create_results', Base.metadata.tables)
        self.assertIn('plm.ai_prompt_activation_results', Base.metadata.tables)
        self.assertIn('plm.ai_prompt_retire_results', Base.metadata.tables)
        self.assertIn('plm.ai_tasks', Base.metadata.tables)
        self.assertIn('plm.ai_task_input_refs', Base.metadata.tables)
        self.assertIn('plm.ai_egress_authorization_snapshots', Base.metadata.tables)
        self.assertIn('plm.ai_task_retry_generations', Base.metadata.tables)
        self.assertIn('plm.ai_invocations', Base.metadata.tables)
        self.assertIn('plm.ai_invocation_context_refs', Base.metadata.tables)
        self.assertIn('plm.ai_egress_previews', Base.metadata.tables)
        self.assertIn('plm.ai_egress_preview_source_refs', Base.metadata.tables)
        self.assertIn('plm.ai_egress_authorizations', Base.metadata.tables)
        self.assertIn('plm.ai_egress_authorization_revocations', Base.metadata.tables)
        self.assertIn('plm.ai_egress_authorize_results', Base.metadata.tables)
        self.assertIn('plm.ai_egress_revoke_results', Base.metadata.tables)
        self.assertIn('plm.ai_execution_content_plans', Base.metadata.tables)
        self.assertIn('plm.ai_execution_content_sources', Base.metadata.tables)
        self.assertIn('plm.ai_suggestion_payloads', Base.metadata.tables)
        self.assertIn('plm.ai_suggestion_evidence_refs', Base.metadata.tables)
        self.assertIn('plm.rag_document_chunks', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_indexes', Base.metadata.tables)
        self.assertIn('plm.rag_index_source_chunks', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_records', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_builds', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_build_batches', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_index_validations', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_index_quality_results', Base.metadata.tables)
        self.assertIn('plm.rag_embedding_index_activation_results', Base.metadata.tables)
        self.assertIn('plm.rag_retrieval_runs', Base.metadata.tables)
        self.assertIn('plm.rag_retrieval_query_contents', Base.metadata.tables)
        self.assertIn('plm.rag_retrieval_candidates', Base.metadata.tables)
        self.assertIn('plm.rag_retrieval_score_parts', Base.metadata.tables)
        self.assertIn('plm.rag_context_bundles', Base.metadata.tables)
        self.assertIn('plm.rag_context_items', Base.metadata.tables)
        for table in (
            'plm.cap_baselines', 'plm.cap_baseline_versions', 'plm.cap_items',
            'plm.cap_item_document_refs', 'plm.cap_item_evidence_refs',
        ):
            self.assertIn(table, Base.metadata.tables)
        for table in (
            'plm.req_packages', 'plm.req_requirements',
            'plm.req_package_memberships', 'plm.req_package_create_results',
            'plm.req_requirement_create_results', 'plm.req_package_command_results',
            'plm.req_requirement_state_decisions',
            'plm.req_requirement_decision_evidence_refs',
            'plm.req_requirement_command_results',
            'plm.req_requirement_versions',
            'plm.req_sources', 'plm.req_acceptance_criteria',
            'plm.req_capability_assessments', 'plm.req_assumptions',
            'plm.req_exclusions', 'plm.req_dependencies',
            'plm.req_source_evidence_refs',
            'plm.req_assessment_evidence_refs',
            'plm.req_version_ai_task_refs',
            'plm.req_requirement_version_create_results',
            'plm.req_requirement_review_state_results',
            'plm.req_relations',
        ):
            self.assertIn(table, Base.metadata.tables)
        for table in (
            'plm.hnd_analyses', 'plm.hnd_analysis_versions',
            'plm.hnd_analysis_source_document_refs', 'plm.hnd_analysis_ai_task_refs',
            'plm.hnd_analysis_items', 'plm.hnd_item_evidence_refs',
            'plm.hnd_item_capability_refs', 'plm.hnd_item_options',
            'plm.hnd_action_items', 'plm.hnd_action_response_refs',
            'plm.hnd_action_evidence_refs', 'plm.hnd_action_state_events',
        ):
            self.assertIn(table, Base.metadata.tables)
        for table in (
            'plm.srv_surveys', 'plm.srv_survey_versions', 'plm.srv_questions',
            'plm.srv_question_options', 'plm.srv_question_source_refs',
            'plm.srv_target_departments', 'plm.srv_rounds',
            'plm.srv_round_source_records', 'plm.srv_assignments',
            'plm.srv_responses', 'plm.srv_answers',
            'plm.srv_answer_evidence_refs', 'plm.srv_conclusions',
            'plm.srv_department_conclusions', 'plm.srv_module_conclusions',
            'plm.srv_conclusion_evidence_refs',
            'plm.srv_conclusion_open_issues',
        ):
            self.assertIn(table, Base.metadata.tables)
        prototype_tables = {
            'plm.prt_packages', 'plm.prt_prototypes',
            'plm.prt_package_memberships', 'plm.prt_scope_decisions',
            'plm.prt_scope_decision_requirement_refs',
            'plm.prt_package_create_results', 'plm.prt_prototype_create_results',
            'plm.prt_package_command_results',
            'plm.prt_prototype_command_results',
            'plm.prt_scope_decision_results',
            'plm.prt_templates', 'plm.prt_template_versions',
            'plm.prt_template_artifact_refs',
            'plm.prt_template_command_results',
            'plm.prt_prototype_versions',
            'plm.prt_version_artifact_refs',
            'plm.prt_version_requirement_refs',
            'plm.prt_interaction_specs',
            'plm.prt_version_create_results',
            'plm.prt_version_review_state_results',
            'plm.prt_version_approval_trace_manifests',
            'plm.prt_version_approval_trace_sources',
            'plm.prt_requirement_links',
        }
        for table in prototype_tables:
            self.assertIn(table, Base.metadata.tables)
        for table in ('plm.sol_outlines', 'plm.sol_outline_create_results',
                      'plm.sol_sections', 'plm.sol_section_create_results',
                      'plm.sol_outline_versions', 'plm.sol_outline_sections',
                      'plm.sol_outline_requirement_refs', 'plm.sol_section_versions',
                      'plm.sol_section_requirement_refs', 'plm.sol_section_evidence_refs',
                      'plm.sol_reference_solutions', 'plm.sol_reference_versions',
                      'plm.sol_reference_revise_results',
                      'plm.sol_reference_document_refs', 'plm.sol_reference_evidence_refs',
                      'plm.sol_reference_deidentification_confirmations'):
            self.assertIn(table, Base.metadata.tables)
            historical_metadata.discard(table)
        self.assertIn('plm.job_parse_cancel_versions', Base.metadata.tables)
        self.assertIn('plm.plt_maintenance_state', Base.metadata.tables)
        for table in (export_orm.exports, export_orm.members, export_orm.captures, export_orm.acceptances):
            self.assertIn("plm."+table.name, Base.metadata.tables)
        self.assertEqual(historical_metadata - {"plm."+t.name for t in (export_orm.exports, export_orm.members, export_orm.captures, export_orm.acceptances, export_orm.render_attempts, export_orm.results, export_orm.cancel_versions, export_orm.retry_generations)} - {"plm.trc_links"} - {"plm."+t.name for t in review_orm._tables} - prototype_tables, {"plm.wfl_checklist_records", "plm.wfl_checklist_record_refs", "plm.wfl_stage_transitions", "plm.wfl_transition_gate_items", "plm.wfl_transition_gate_refs", "plm.wfl_project_workflows", "plm.wfl_stages", "plm.wfl_stage_checklists", "plm.wfl_checklist_items", "plm.plt_system_configurations", "plm.plt_configuration_versions", "plm.plt_configuration_command_receipts", "plm.plt_idempotency_receipts", "plm.plt_secret_records", "plm.plt_secret_versions", "plm.aud_events", "plm.auth_users", "plm.auth_password_credentials", "plm.auth_sessions", "plm.auth_login_rate_buckets", "plm.lic_installations", "plm.lic_validation_events", "plm.lic_validation_states", "plm.lic_installation_documents", "plm.lic_trusted_time_events", "plm.lic_trusted_time_states", "plm.prj_projects", "plm.prj_departments", "plm.prj_department_create_results", "plm.prj_department_deactivate_results", "plm.prj_project_members", "plm.prj_member_assignment_history", "plm.prj_member_create_results", "plm.prj_member_state_results", "plm.doc_file_objects", "plm.doc_file_state_events", "plm.doc_documents", "plm.doc_document_versions", "plm.doc_version_source_refs", "plm.doc_upload_intents", "plm.doc_parse_records", "plm.doc_parse_result_refs", "plm.evd_evidence_records", "plm.job_jobs", "plm.job_attempts", "plm.job_leases", "plm.job_outbox_events", "plm.job_outbox_consumptions"})


if __name__ == "__main__":
    unittest.main()
