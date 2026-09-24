from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RootSpec:
    root_id: str
    table: str
    pk: str
    profile: str


ROOTS: tuple[RootSpec, ...] = (
    RootSpec("PLT-01", "plt_system_configurations", "system_configuration_id", "M-DEP"),
    RootSpec("PLT-02", "plt_secret_records", "secret_record_id", "SEC-DEP"),
    RootSpec("AUT-01", "auth_users", "user_id", "M-DEP"),
    RootSpec("AUT-02", "auth_sessions", "session_id", "R-DEP"),
    RootSpec("PRJ-01", "prj_projects", "project_id", "M-DEP"),
    RootSpec("PRJ-02", "prj_project_members", "project_member_id", "M-PRJ"),
    RootSpec("PRJ-03", "prj_departments", "department_id", "M-PRJ"),
    RootSpec("WFL-01", "wfl_project_workflows", "workflow_id", "M-PRJ"),
    RootSpec("WFL-02", "wfl_stage_transitions", "stage_transition_id", "A-PRJ"),
    RootSpec("RVW-01", "rvw_reviews", "review_id", "M-SCP"),
    RootSpec("RVW-02", "rvw_review_rounds", "review_round_id", "A-SCP"),
    RootSpec("TRC-01", "trc_links", "trace_link_id", "A-SCP"),
    RootSpec("AUD-01", "aud_events", "audit_event_id", "A-DEP"),
    RootSpec("LIC-01", "lic_installations", "license_installation_id", "SEC-DEP"),
    RootSpec("LIC-02", "lic_validation_states", "license_validation_state_id", "SEC-DEP"),
    RootSpec("LIC-03", "lic_trusted_time_states", "trusted_time_state_id", "SEC-DEP"),
    RootSpec("DOC-01", "doc_documents", "document_id", "M-SCP"),
    RootSpec("DOC-02", "doc_document_versions", "document_version_id", "V-SCP"),
    RootSpec("DOC-03", "doc_file_objects", "file_object_id", "M-SCP"),
    RootSpec("DOC-04", "doc_parse_records", "parse_record_id", "R-SCP"),
    RootSpec("EVD-01", "evd_evidence_records", "evidence_id", "M-SCP"),
    RootSpec("EVD-02", "evd_bindings", "evidence_binding_id", "A-SCP"),
    RootSpec("JOB-01", "job_jobs", "job_id", "R-SCP"),
    RootSpec("JOB-02", "job_outbox_events", "outbox_event_id", "A-SCP"),
    RootSpec("AI-01", "ai_providers", "ai_provider_id", "M-DEP"),
    RootSpec("AI-02", "ai_models", "ai_model_id", "M-DEP"),
    RootSpec("AI-03", "ai_prompt_templates", "prompt_template_id", "M-DEP"),
    RootSpec("AI-04", "ai_tasks", "ai_task_id", "R-SCP"),
    RootSpec("RAG-01", "rag_document_chunks", "chunk_id", "M-SCP"),
    RootSpec("RAG-02", "rag_embedding_indexes", "embedding_index_id", "M-SCP"),
    RootSpec("RAG-03", "rag_embedding_records", "embedding_record_id", "R-SCP"),
    RootSpec("RAG-04", "rag_retrieval_runs", "retrieval_run_id", "R-SCP"),
    RootSpec("CAP-01", "cap_baselines", "baseline_id", "M-GLB"),
    RootSpec("CAP-02", "cap_baseline_versions", "baseline_version_id", "V-GLB"),
    RootSpec("HND-01", "hnd_analyses", "handover_analysis_id", "M-PRJ"),
    RootSpec("HND-02", "hnd_analysis_versions", "handover_analysis_version_id", "V-PRJ"),
    RootSpec("HND-03", "hnd_action_items", "action_item_id", "M-PRJ"),
    RootSpec("SRV-01", "srv_surveys", "survey_id", "M-PRJ"),
    RootSpec("SRV-02", "srv_survey_versions", "survey_version_id", "V-PRJ"),
    RootSpec("SRV-03", "srv_rounds", "survey_round_id", "M-PRJ"),
    RootSpec("SRV-04", "srv_assignments", "survey_assignment_id", "M-PRJ"),
    RootSpec("SRV-05", "srv_conclusions", "survey_conclusion_id", "V-PRJ"),
    RootSpec("REQ-01", "req_packages", "requirement_package_id", "M-PRJ"),
    RootSpec("REQ-02", "req_requirements", "requirement_id", "M-PRJ"),
    RootSpec("REQ-03", "req_requirement_versions", "requirement_version_id", "V-PRJ"),
    RootSpec("REQ-04", "req_relations", "requirement_relation_id", "A-PRJ"),
    RootSpec("PRT-01", "prt_packages", "prototype_package_id", "M-PRJ"),
    RootSpec("PRT-02", "prt_prototypes", "prototype_id", "M-PRJ"),
    RootSpec("PRT-03", "prt_prototype_versions", "prototype_version_id", "V-PRJ"),
    RootSpec("PRT-04", "prt_templates", "prototype_template_id", "M-SCP"),
    RootSpec("PRT-05", "prt_requirement_links", "requirement_prototype_link_id", "A-PRJ"),
    RootSpec("SOL-01", "sol_reference_solutions", "reference_solution_id", "M-SCP"),
    RootSpec("SOL-02", "sol_outlines", "solution_outline_id", "M-PRJ"),
    RootSpec("SOL-03", "sol_outline_versions", "solution_outline_version_id", "V-PRJ"),
    RootSpec("SOL-04", "sol_sections", "solution_section_id", "M-PRJ"),
    RootSpec("SOL-05", "sol_section_versions", "solution_section_version_id", "V-PRJ"),
    RootSpec("SOL-06", "sol_structured_specs", "structured_solution_spec_id", "V-PRJ"),
    RootSpec("PLN-01", "pln_plans", "plan_id", "M-PRJ"),
    RootSpec("PLN-02", "pln_plan_versions", "plan_version_id", "V-PRJ"),
    RootSpec("PLN-03", "pln_reference_plans", "reference_plan_id", "M-SCP"),
    RootSpec("OUT-01", "out_requests", "output_request_id", "R-PRJ"),
    RootSpec("OUT-02", "out_artifacts", "output_artifact_id", "M-PRJ"),
    RootSpec("PLG-01", "plg_packages", "plugin_package_id", "SEC-DEP"),
    RootSpec("PLG-02", "plg_installations", "plugin_installation_id", "M-DEP"),
    RootSpec("PLG-03", "plg_executions", "plugin_execution_id", "R-PRJ"),
)


QUERY_IDS: tuple[str, ...] = (
    "Q-AUTH-01", "Q-PRJ-01", "Q-PRJ-02", "Q-WFL-01", "Q-VER-01",
    "Q-RVW-01", "Q-DOC-01", "Q-EVD-01", "Q-TRC-01", "Q-AUD-01",
    "Q-JOB-01", "Q-JOB-02", "Q-OUT-01", "Q-RET-01", "Q-RAG-01",
    "Q-RAG-02", "Q-REQ-01", "Q-WBS-01", "Q-PLG-01", "Q-OUTPUT-01",
)


VALIDATION_ONLY = True
SCHEMA_CONTRACT_VERSION = "sc-04.validation.v1"
