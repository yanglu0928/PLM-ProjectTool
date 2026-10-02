"""AI-04 Task, immutable Invocation attempts, context, and egress evidence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_TASK_TYPES = (
    "'DOCUMENT_PARSE','CAPABILITY_EXTRACT','GAP_ANALYSIS','SURVEY_GENERATE',"
    "'SURVEY_ANALYZE','REQUIREMENT_NORMALIZE','REQUIREMENT_MATCH',"
    "'SOLUTION_SUGGEST','PROTOTYPE_GENERATE','SOLUTION_GENERATE',"
    "'PLAN_GENERATE','OUTPUT_SUMMARIZE'"
)


class AITaskRow(Base):
    __tablename__ = "ai_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["current_invocation_ref", "ai_task_id"],
            ["plm.ai_invocations.ai_invocation_id", "plm.ai_invocations.ai_task_id"],
            name="fk_ai_tasks__current_invocation", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_tasks__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["requested_by"], ["plm.auth_users.user_id"],
                             name="fk_ai_tasks__requester", ondelete="NO ACTION"),
        ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                             name="fk_ai_tasks__job", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["prompt_template_ref", "prompt_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_tasks__prompt_version", ondelete="NO ACTION",
        ),
        UniqueConstraint("ai_task_id", "scope", "project_id",
                         name="uq_ai_tasks__identity_scope", postgresql_nulls_not_distinct=True),
        CheckConstraint("ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND requested_by <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid",
                        name="ck_ai_tasks__ids"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_tasks__scope"),
        CheckConstraint(f"task_type IN ({_TASK_TYPES})", name="ck_ai_tasks__task_type"),
        CheckConstraint("octet_length(input_fingerprint)=32 AND "
                        "prompt_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
                        "output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
                        "context_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
                        name="ck_ai_tasks__policy"),
        CheckConstraint("task_state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED',"
                        "'CANCEL_REQUESTED','CANCELLED') AND "
                        "suggestion_state IN ('NONE','AVAILABLE','ACCEPTED_TO_DRAFT',"
                        "'REJECTED','SUPERSEDED') AND "
                        "(suggestion_state='NONE' OR task_state='SUCCEEDED') AND lock_version>=0",
                        name="ck_ai_tasks__state"),
        CheckConstraint("(suggestion_state='ACCEPTED_TO_DRAFT' AND "
                        "accepted_domain_module IN ('handover','survey','requirement',"
                        "'prototype','solution','plan') AND accepted_domain_version_id IS NOT NULL) OR "
                        "(suggestion_state<>'ACCEPTED_TO_DRAFT' AND "
                        "accepted_domain_module IS NULL AND accepted_domain_version_id IS NULL)",
                        name="ck_ai_tasks__accepted"),
        CheckConstraint("(started_at IS NULL OR started_at>=requested_at) AND "
                        "(completed_at IS NULL OR (started_at IS NOT NULL AND completed_at>=started_at)) "
                        "AND isfinite(requested_at) AND isfinite(created_at) AND "
                        "(started_at IS NULL OR isfinite(started_at)) AND "
                        "(completed_at IS NULL OR isfinite(completed_at))",
                        name="ck_ai_tasks__time"),
        CheckConstraint("error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                        name="ck_ai_tasks__error"),
        CheckConstraint(
            "(prompt_template_ref IS NULL AND prompt_version_no IS NULL "
            "AND task_parameters IS NULL AND task_parameters_fingerprint IS NULL) OR "
            "(prompt_template_ref IS NOT NULL "
            "AND prompt_template_ref<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_version_no BETWEEN 1 AND 9223372036854775807 "
            "AND jsonb_typeof(task_parameters)='object' "
            "AND octet_length(task_parameters_fingerprint)=32)",
            name="ck_ai_tasks__submission_snapshot",
        ),
        Index("ix_ai_tasks__project_state", "project_id", "task_state",
              text("requested_at DESC"), text("ai_task_id DESC")),
        Index("ix_ai_tasks__requester", "requested_by", text("requested_at DESC")),
        Index("uq_ai_tasks__job_ref", "job_ref", unique=True,
              postgresql_where=text("job_ref IS NOT NULL")),
        Index("ix_ai_tasks__prompt_version", "prompt_template_ref", "prompt_version_no"),
    )

    ai_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    prompt_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_ref: Mapped[str] = mapped_column(Text, nullable=False)
    context_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    prompt_version_no: Mapped[int | None] = mapped_column(BigInteger)
    task_parameters: Mapped[dict | None] = mapped_column(JSONB)
    task_parameters_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    task_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'QUEUED'"))
    suggestion_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'NONE'"))
    accepted_domain_module: Mapped[str | None] = mapped_column(Text)
    accepted_domain_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    current_invocation_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    job_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class AITaskInputRefRow(Base):
    __tablename__ = "ai_task_input_refs"
    __table_args__ = (
        ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                             name="fk_ai_task_inputs__task", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_task_inputs__project", ondelete="NO ACTION"),
        UniqueConstraint("ai_task_id", "ref_ordinal", name="uq_ai_task_inputs__ordinal"),
        CheckConstraint("input_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND ref_ordinal BETWEEN 1 AND 1000", name="ck_ai_task_inputs__ids"),
        CheckConstraint("object_id IS NULL OR "
                        "object_id <> '00000000-0000-0000-0000-000000000000'::uuid",
                        name="ck_ai_task_inputs__object_id"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_task_inputs__scope"),
        CheckConstraint("owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
                        "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND isfinite(added_at)",
                        name="ck_ai_task_inputs__ref"),
        Index("ix_ai_task_inputs__object_version", "owner_module", "object_type",
              "object_id", "version_id"),
    )

    input_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    ai_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ref_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL is migration-only legacy from Schema0063; all new INSERTs are guarded non-NULL.
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class AIEgressAuthorizationSnapshotRow(Base):
    """Immutable per-task proof of the data egress decision; contains no secret."""

    __tablename__ = "ai_egress_authorization_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                             name="fk_ai_egress_snapshots__task", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_egress_snapshots__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_egress_snapshots__provider_config", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["approved_by"], ["plm.auth_users.user_id"],
                             name="fk_ai_egress_snapshots__approver", ondelete="NO ACTION"),
        ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                             name="fk_ai_egress_snapshots__model", ondelete="NO ACTION"),
        UniqueConstraint("egress_authorization_snapshot_id", "ai_task_id",
                         name="uq_ai_egress_snapshots__identity_task"),
        CheckConstraint(
            "egress_authorization_snapshot_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND authorization_ref <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND approved_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_egress_snapshots__ids",
        ),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_egress_snapshots__scope"),
        CheckConstraint(
            "purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND data_region ~ '^[a-z][a-z0-9-]{0,63}$' "
            "AND jsonb_typeof(allowed_data_categories)='array' "
            "AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64 "
            "AND octet_length(authorization_fingerprint)=32",
            name="ck_ai_egress_snapshots__policy",
        ),
        CheckConstraint(
            "approved_at<=captured_at AND captured_at<valid_until "
            "AND isfinite(approved_at) AND isfinite(valid_until) AND isfinite(captured_at)",
            name="ck_ai_egress_snapshots__time",
        ),
        CheckConstraint(
            "(ai_model_id IS NULL AND approved_role IS NULL "
            "AND preview_payload_fingerprint IS NULL AND source_refs_fingerprint IS NULL "
            "AND max_payload_bytes IS NULL AND max_input_tokens IS NULL "
            "AND max_retry_attempts IS NULL AND authorization_state_at_capture IS NULL) OR "
            "(ai_model_id IS NOT NULL AND approved_role IN "
            "('PROJECT_MANAGER','CUSTOMER_MANAGER','DEPLOYMENT_ADMIN') "
            "AND octet_length(preview_payload_fingerprint)=32 "
            "AND octet_length(source_refs_fingerprint)=32 "
            "AND max_payload_bytes BETWEEN 1 AND 1073741824 "
            "AND max_input_tokens BETWEEN 1 AND 1048576 "
            "AND max_retry_attempts BETWEEN 1 AND 10 "
            "AND authorization_state_at_capture='AUTHORIZED')",
            name="ck_ai_egress_snapshots__complete_v2",
        ),
        Index("ix_ai_egress_snapshots__task_time", "ai_task_id", "captured_at"),
        Index("ix_ai_egress_snapshots__model", "ai_model_id"),
    )

    egress_authorization_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    ai_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    authorization_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose_ref: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_region: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    authorization_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_role: Mapped[str | None] = mapped_column(Text)
    preview_payload_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    source_refs_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    max_payload_bytes: Mapped[int | None] = mapped_column(BigInteger)
    max_input_tokens: Mapped[int | None] = mapped_column(Integer)
    max_retry_attempts: Mapped[int | None] = mapped_column(Integer)
    authorization_state_at_capture: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class AIInvocationRow(Base):
    """One retry-safe AI attempt with fingerprints and controlled references only."""

    __tablename__ = "ai_invocations"
    __table_args__ = (
        ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                             name="fk_ai_invocations__task", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_invocations__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_invocations__provider_config", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                             name="fk_ai_invocations__model", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["prompt_template_id", "prompt_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_invocations__prompt_version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["egress_authorization_snapshot_id", "ai_task_id"],
            ["plm.ai_egress_authorization_snapshots.egress_authorization_snapshot_id",
             "plm.ai_egress_authorization_snapshots.ai_task_id"],
            name="fk_ai_invocations__egress_task", ondelete="NO ACTION",
        ),
        UniqueConstraint("ai_task_id", "attempt_no", name="uq_ai_invocations__task_attempt"),
        UniqueConstraint("ai_invocation_id", "ai_task_id", name="uq_ai_invocations__identity_task"),
        CheckConstraint(
            "ai_invocation_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_invocations__ids",
        ),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_invocations__scope"),
        CheckConstraint(
            "attempt_no BETWEEN 1 AND 2147483647 AND prompt_version_no>0 AND schema_version>0 "
            "AND lock_version>=0 AND octet_length(input_fingerprint)=32 "
            "AND octet_length(request_payload_fingerprint)=32 "
            "AND (response_fingerprint IS NULL OR octet_length(response_fingerprint)=32) "
            "AND (context_bundle_fingerprint IS NULL OR octet_length(context_bundle_fingerprint)=32)",
            name="ck_ai_invocations__version_fingerprint",
        ),
        CheckConstraint(
            "model_revision_observed ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' "
            "AND output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND (provider_request_ref IS NULL OR (char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]'))",
            name="ck_ai_invocations__refs",
        ),
        CheckConstraint(
            "(egress_authorization_mode='AUTHORIZED' AND egress_authorization_snapshot_id IS NOT NULL) OR "
            "(egress_authorization_mode='NOT_APPLICABLE' AND egress_authorization_snapshot_id IS NULL)",
            name="ck_ai_invocations__egress"),
        CheckConstraint(
            "invocation_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED') "
            "AND schema_validation_state IN ('NOT_APPLICABLE','PENDING','VALID','INVALID') "
            "AND ((schema_validation_required AND schema_validation_state<>'NOT_APPLICABLE') "
            "OR (NOT schema_validation_required AND schema_validation_state='NOT_APPLICABLE'))",
            name="ck_ai_invocations__state"),
        CheckConstraint(
            "(invocation_state NOT IN ('SUCCEEDED','FAILED','CANCELLED') AND completed_at IS NULL) OR "
            "(invocation_state IN ('SUCCEEDED','FAILED','CANCELLED') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) "
            "AND (invocation_state<>'SUCCEEDED' OR (response_fingerprint IS NOT NULL "
            "AND ((schema_validation_required AND schema_validation_state='VALID') "
            "OR (NOT schema_validation_required AND schema_validation_state='NOT_APPLICABLE')))) "
            "AND (invocation_state<>'FAILED' OR (error_code IS NOT NULL AND retryable IS NOT NULL))",
            name="ck_ai_invocations__terminal"),
        CheckConstraint(
            "(suggestion_payload_ref IS NULL OR (invocation_state='SUCCEEDED' "
            "AND schema_validation_state='VALID')) "
            "AND (error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (usage_input_tokens IS NULL OR usage_input_tokens>=0) "
            "AND (usage_output_tokens IS NULL OR usage_output_tokens>=0) "
            "AND (latency_ms IS NULL OR latency_ms>=0)",
            name="ck_ai_invocations__result"),
        CheckConstraint(
            "(started_at IS NULL OR started_at>=created_at) "
            "AND (completed_at IS NULL OR completed_at>=started_at) "
            "AND isfinite(created_at) AND (started_at IS NULL OR isfinite(started_at)) "
            "AND (completed_at IS NULL OR isfinite(completed_at))",
            name="ck_ai_invocations__time"),
        Index("ix_ai_invocations__task_state", "ai_task_id", "invocation_state", "attempt_no"),
        Index("ix_ai_invocations__provider_time", "ai_provider_id", "created_at"),
    )

    ai_invocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    ai_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_revision_observed: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prompt_version_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_schema_ref: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    egress_authorization_mode: Mapped[str] = mapped_column(Text, nullable=False)
    egress_authorization_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_payload_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    retrieval_run_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    context_bundle_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    invocation_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    schema_validation_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schema_validation_state: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_payload_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    response_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    usage_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    usage_output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)
    provider_request_ref: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class AIInvocationContextRefRow(Base):
    """Immutable ordered version references used to assemble an Invocation context."""

    __tablename__ = "ai_invocation_context_refs"
    __table_args__ = (
        ForeignKeyConstraint(["ai_invocation_id"], ["plm.ai_invocations.ai_invocation_id"],
                             name="fk_ai_invocation_contexts__invocation", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_invocation_contexts__project", ondelete="NO ACTION"),
        UniqueConstraint("ai_invocation_id", "ref_ordinal",
                         name="uq_ai_invocation_contexts__ordinal"),
        CheckConstraint(
            "context_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_invocation_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ref_ordinal BETWEEN 1 AND 10000",
            name="ck_ai_invocation_contexts__ids"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_invocation_contexts__scope"),
        CheckConstraint(
            "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' "
            "AND object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' "
            "AND octet_length(content_fingerprint)=32 AND isfinite(added_at)",
            name="ck_ai_invocation_contexts__ref"),
        Index("ix_ai_invocation_contexts__version", "owner_module", "object_type", "version_id"),
    )

    context_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    ai_invocation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ref_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
