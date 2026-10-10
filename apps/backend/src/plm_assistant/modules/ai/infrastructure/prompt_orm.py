"""AI-03 deployment prompt identity and immutable versions; no runtime registry."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class PromptTemplateRow(Base):
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prompt_template_id", "active_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_prompt_templates__active_version", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        CheckConstraint("prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid",
                        name="ck_ai_prompt_templates__ids"),
        CheckConstraint("task_type IN ('DOCUMENT_PARSE','CAPABILITY_EXTRACT','GAP_ANALYSIS',"
                        "'SURVEY_GENERATE','SURVEY_ANALYZE','REQUIREMENT_NORMALIZE',"
                        "'REQUIREMENT_MATCH','SOLUTION_SUGGEST','PROTOTYPE_GENERATE',"
                        "'SOLUTION_GENERATE','PLAN_GENERATE','OUTPUT_SUMMARIZE')",
                        name="ck_ai_prompt_templates__task_type"),
        CheckConstraint("scope = 'DEPLOYMENT' AND template_state IN ('DRAFT','ACTIVE','RETIRED') "
                        "AND (template_state <> 'DRAFT' OR active_version_no IS NULL) "
                        "AND (template_state <> 'ACTIVE' OR active_version_no IS NOT NULL) "
                        "AND lock_version >= 0 AND isfinite(created_at)",
                        name="ck_ai_prompt_templates__state"),
    )

    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DEPLOYMENT'"))
    template_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    active_version_no: Mapped[int | None] = mapped_column(BigInteger)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class PromptVersionRow(Base):
    __tablename__ = "ai_prompt_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0 AND version_no <= 9223372036854775807 "
                        "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid "
                        "AND length(system_template) BETWEEN 1 AND 65536 "
                        "AND length(user_template) BETWEEN 1 AND 65536 "
                        "AND system_template_hash ~ '^[0-9a-f]{64}$' "
                        "AND user_template_hash ~ '^[0-9a-f]{64}$' "
                        "AND output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                        "AND schema_version BETWEEN 1 AND 2147483647 "
                        "AND rag_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                        "AND provider_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                        "AND isfinite(created_at)",
                        name="ck_ai_prompt_versions__shape"),
    )

    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.ai_prompt_templates.prompt_template_id", ondelete="NO ACTION"),
        primary_key=True,
    )
    version_no: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    system_template_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_template_hash: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_ref: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rag_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    provider_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class PromptVersionCreateResultRow(Base):
    __tablename__ = "ai_prompt_version_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prompt_template_id", "version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_prompt_version_create_results__version", ondelete="NO ACTION",
        ),
        UniqueConstraint("prompt_template_id", "version_no",
                         name="uq_ai_prompt_version_create_results__version"),
        UniqueConstraint("audit_event_id", name="uq_ai_prompt_version_create_results__audit"),
        CheckConstraint(
            "result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_no > 0 AND octet_length(content_fingerprint) = 32 "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_prompt_version_create_results__shape",
        ),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    audit_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.aud_events.audit_event_id", ondelete="NO ACTION"), nullable=False,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                             server_default=text("txid_current()"))


class PromptActivationResultRow(Base):
    __tablename__ = "ai_prompt_activation_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prompt_template_id", "version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_prompt_activation_results__version", ondelete="NO ACTION",
        ),
        UniqueConstraint("audit_event_id", name="uq_ai_prompt_activation_results__audit"),
        CheckConstraint(
            "result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_no > 0 AND state = 'ACTIVE' "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_prompt_activation_results__shape",
        ),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    audit_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.aud_events.audit_event_id", ondelete="NO ACTION"), nullable=False,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                             server_default=text("txid_current()"))


class PromptRetireResultRow(Base):
    __tablename__ = "ai_prompt_retire_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prompt_template_id", "prior_active_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_prompt_retire_results__prior_version", ondelete="NO ACTION",
        ),
        UniqueConstraint("audit_event_id", name="uq_ai_prompt_retire_results__audit"),
        CheckConstraint(
            "result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND state = 'RETIRED' "
            "AND ((prior_state = 'DRAFT' AND prior_active_version_no IS NULL) "
            "OR (prior_state = 'ACTIVE' AND prior_active_version_no IS NOT NULL "
            "AND prior_active_version_no > 0)) "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_prompt_retire_results__shape",
        ),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.ai_prompt_templates.prompt_template_id",
                                      name="fk_ai_prompt_retire_results__template", ondelete="NO ACTION"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    audit_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.aud_events.audit_event_id", ondelete="NO ACTION"), nullable=False,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prior_state: Mapped[str] = mapped_column(Text, nullable=False)
    prior_active_version_no: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                             server_default=text("txid_current()"))
