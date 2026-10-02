"""AI-04 Task identity and immutable input references; no Invocation execution."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
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
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_ai_tasks__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["requested_by"], ["plm.auth_users.user_id"],
                             name="fk_ai_tasks__requester", ondelete="NO ACTION"),
        ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                             name="fk_ai_tasks__job", ondelete="NO ACTION"),
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
        Index("ix_ai_tasks__project_state", "project_id", "task_state",
              text("requested_at DESC"), text("ai_task_id DESC")),
        Index("ix_ai_tasks__requester", "requested_by", text("requested_at DESC")),
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
    task_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'QUEUED'"))
    suggestion_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'NONE'"))
    accepted_domain_module: Mapped[str | None] = mapped_column(Text)
    accepted_domain_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
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
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_ai_task_inputs__scope"),
        CheckConstraint("owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
                        "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND isfinite(added_at)",
                        name="ck_ai_task_inputs__ref"),
        Index("ix_ai_task_inputs__version", "owner_module", "object_type", "version_id"),
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
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
