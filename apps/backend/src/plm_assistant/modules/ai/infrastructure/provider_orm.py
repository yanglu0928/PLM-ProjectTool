"""AI-01 deployment Provider identity and immutable configuration history."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class AIProviderRow(Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        CheckConstraint("provider_state IN ('CONFIGURED','ACTIVE','SUSPENDED','RETIRED') AND lock_version >= 0", name="ck_ai_providers__state"),
        CheckConstraint("ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND current_config_version_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_providers__ids"),
        ForeignKeyConstraint(
            ["current_config_version_ref", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id", "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_providers__current_config", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        Index("ix_ai_providers__current_config", "current_config_version_ref", "ai_provider_id"),
    )

    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    current_config_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'CONFIGURED'"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))


class AIProviderConfigVersionRow(Base):
    __tablename__ = "ai_provider_config_versions"
    __table_args__ = (
        UniqueConstraint("provider_config_version_id", "ai_provider_id", name="uq_ai_provider_configs__id_provider"),
        UniqueConstraint("provider_config_version_id", "ai_provider_id", "secret_ref", name="uq_ai_provider_configs__identity_secret"),
        UniqueConstraint("ai_provider_id", "config_version_no", name="uq_ai_provider_configs__provider_no"),
        CheckConstraint("provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND secret_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_provider_configs__ids"),
        CheckConstraint("config_version_no > 0 AND created_xid > 0", name="ck_ai_provider_configs__version"),
        CheckConstraint("provider_kind IN ('OPENAI_COMPATIBLE','ANTHROPIC_MESSAGES','GEMINI_NATIVE','CUSTOM')", name="ck_ai_provider_configs__kind"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 120 AND char_length(btrim(display_name)) > 0", name="ck_ai_provider_configs__display_name"),
        CheckConstraint("char_length(endpoint_policy_ref) BETWEEN 1 AND 128 AND endpoint_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:-]*$'", name="ck_ai_provider_configs__endpoint_ref"),
        CheckConstraint("char_length(data_region) BETWEEN 1 AND 64 AND data_region ~ '^[a-z][a-z0-9-]*$'", name="ck_ai_provider_configs__region"),
        CheckConstraint("char_length(egress_class) BETWEEN 1 AND 64 AND egress_class ~ '^[A-Z][A-Z0-9_]*$'", name="ck_ai_provider_configs__egress"),
        CheckConstraint("can_chat OR can_structured_output OR can_embedding OR can_rerank", name="ck_ai_provider_configs__capabilities"),
        Index("ix_ai_provider_configs__secret", "secret_ref"),
        Index("ix_ai_provider_configs__creator", "created_by"),
    )

    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.ai_providers.ai_provider_id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"), nullable=False)
    config_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_kind: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    secret_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.plt_secret_records.secret_record_id", ondelete="NO ACTION"), nullable=False)
    data_region: Mapped[str] = mapped_column(Text, nullable=False)
    egress_class: Mapped[str] = mapped_column(Text, nullable=False)
    can_chat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_structured_output: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_rerank: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("txid_current()"))


class AIProviderProbeResultRow(Base):
    """Append-only final probe proof; never a permission to activate by itself."""

    __tablename__ = "ai_provider_probe_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id", "secret_record_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id",
             "plm.ai_provider_config_versions.secret_ref"],
            name="fk_ai_provider_probe_results__config_secret", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["secret_version_id", "secret_record_id"],
            ["plm.plt_secret_versions.secret_version_id", "plm.plt_secret_versions.secret_record_id"],
            name="fk_ai_provider_probe_results__secret_version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["job_id", "attempt_no"], ["plm.job_attempts.job_id", "plm.job_attempts.attempt_no"],
            name="fk_ai_provider_probe_results__attempt", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["job_id", "fencing_token"], ["plm.job_leases.job_id", "plm.job_leases.fencing_token"],
            name="fk_ai_provider_probe_results__lease", ondelete="NO ACTION",
        ),
        UniqueConstraint("job_id", name="uq_ai_provider_probe_results__job"),
        UniqueConstraint("probe_result_id", "ai_provider_id", "provider_config_version_id",
                         name="uq_ai_provider_probe_results__identity_config"),
        CheckConstraint(
            "probe_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND secret_record_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND secret_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND job_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_provider_probe_results__ids",
        ),
        CheckConstraint("probe_id = 'CHAT_CONNECTIVITY_V1'", name="ck_ai_provider_probe_results__probe"),
        CheckConstraint("octet_length(policy_sha256) = 32", name="ck_ai_provider_probe_results__policy_digest"),
        CheckConstraint("attempt_no > 0 AND fencing_token > 0 AND created_xid > 0", name="ck_ai_provider_probe_results__attempt"),
        CheckConstraint(
            "(outcome = 'SUCCEEDED' AND failure_code IS NULL) OR "
            "(outcome = 'FAILED' AND failure_code IS NOT NULL "
            "AND failure_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_ai_provider_probe_results__outcome",
        ),
        CheckConstraint("isfinite(observed_at) AND isfinite(created_at)", name="ck_ai_provider_probe_results__time"),
        Index("ix_ai_provider_probe_results__provider_time", "ai_provider_id", "observed_at", "probe_result_id"),
    )

    probe_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    secret_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    secret_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.job_jobs.job_id", ondelete="NO ACTION"), nullable=False)
    probe_id: Mapped[str] = mapped_column(Text, nullable=False)
    policy_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(Text)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("txid_current()"))


class AIProviderActivationResultRow(Base):
    """Immutable first ACTIVE response; referenced by an actor-scoped receipt."""

    __tablename__ = "ai_provider_activation_results"
    __table_args__ = (
        ForeignKeyConstraint(["ai_provider_id"], ["plm.ai_providers.ai_provider_id"],
                             name="fk_ai_provider_activation_results__provider", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_provider_activation_results__config_provider", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["probe_result_id", "ai_provider_id", "provider_config_version_id"],
            ["plm.ai_provider_probe_results.probe_result_id",
             "plm.ai_provider_probe_results.ai_provider_id",
             "plm.ai_provider_probe_results.provider_config_version_id"],
            name="fk_ai_provider_activation_results__probe_config", ondelete="NO ACTION"),
        ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                             name="fk_ai_provider_activation_results__actor", ondelete="NO ACTION"),
        ForeignKeyConstraint(["audit_event_id"], ["plm.aud_events.audit_event_id"],
                             name="fk_ai_provider_activation_results__audit", ondelete="NO ACTION"),
        UniqueConstraint("ai_provider_id", "lock_version",
                         name="uq_ai_provider_activation_results__provider_version"),
        UniqueConstraint("audit_event_id", name="uq_ai_provider_activation_results__audit"),
        CheckConstraint(
            "activation_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND probe_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND before_state IN ('CONFIGURED','SUSPENDED') AND result_state = 'ACTIVE' "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_provider_activation_results__shape",
        ),
    )

    activation_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    probe_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before_state: Mapped[str] = mapped_column(Text, nullable=False)
    result_state: Mapped[str] = mapped_column(Text, nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                   server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                              server_default=text("txid_current()"))
