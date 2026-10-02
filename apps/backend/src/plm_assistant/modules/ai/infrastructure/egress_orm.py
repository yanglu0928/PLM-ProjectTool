"""AI-owned egress previews and immutable source references."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class AIEgressPreviewRow(Base):
    __tablename__ = "ai_egress_previews"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_ai_egress_previews__project"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_ai_egress_previews__creator"),
        ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"], name="fk_ai_egress_previews__model"),
        ForeignKeyConstraint(["provider_config_version_id", "ai_provider_id"],
                             ["plm.ai_provider_config_versions.provider_config_version_id", "plm.ai_provider_config_versions.ai_provider_id"],
                             name="fk_ai_egress_previews__provider_config"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_ai_egress_previews__scope"),
        CheckConstraint("operation_type IN ('AI_TASK','RETRIEVAL_RUN','INDEX_BUILD','INDEX_REBUILD')", name="ck_ai_egress_previews__operation"),
        CheckConstraint("purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND minimal_payload_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND data_region ~ '^[a-z][a-z0-9-]{0,63}$'", name="ck_ai_egress_previews__refs"),
        CheckConstraint("jsonb_typeof(allowed_data_categories)='array' AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64 AND jsonb_typeof(risk_codes)='array' AND jsonb_array_length(risk_codes) BETWEEN 1 AND 32", name="ck_ai_egress_previews__arrays"),
        CheckConstraint(
            "egress_preview_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_egress_previews__uuid",
        ),
        CheckConstraint("estimated_record_count BETWEEN 0 AND 1000000000 AND max_payload_bytes BETWEEN 1 AND 1073741824 AND max_input_tokens BETWEEN 1 AND 1048576 AND max_retry_attempts BETWEEN 1 AND 10", name="ck_ai_egress_previews__bounds"),
        CheckConstraint("octet_length(payload_fingerprint)=32 AND octet_length(source_refs_fingerprint)=32", name="ck_ai_egress_previews__fingerprints"),
        CheckConstraint("created_at<expires_at AND isfinite(created_at) AND isfinite(expires_at)", name="ck_ai_egress_previews__time"),
        Index("ix_ai_egress_previews__project_time", "project_id", text("created_at DESC"), text("egress_preview_id DESC")),
    )
    egress_preview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purpose_ref: Mapped[str] = mapped_column(Text, nullable=False)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_region: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    minimal_payload_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_payload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_refs_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    risk_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class AIEgressPreviewSourceRefRow(Base):
    __tablename__ = "ai_egress_preview_source_refs"
    __table_args__ = (
        ForeignKeyConstraint(["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"], name="fk_ai_egress_preview_sources__preview"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_ai_egress_preview_sources__project"),
        UniqueConstraint("egress_preview_id", "ref_ordinal", name="uq_ai_egress_preview_sources__ordinal"),
        UniqueConstraint(
            "egress_preview_id",
            "resource_type",
            "owner_module",
            "object_type",
            "object_id",
            "version_id",
            name="uq_ai_egress_preview_sources__semantic",
        ),
        CheckConstraint("ref_ordinal BETWEEN 1 AND 1000 AND resource_type ~ '^[A-Z][A-Z0-9-]{0,63}$' AND owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND object_type ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_ai_egress_preview_sources__shape"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_ai_egress_preview_sources__scope"),
        CheckConstraint(
            "egress_preview_source_ref_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND egress_preview_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_egress_preview_sources__uuid",
        ),
        Index("ix_ai_egress_preview_sources__object", "owner_module", "object_type", "object_id", "version_id"),
    )
    egress_preview_source_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    egress_preview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ref_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))


class AIEgressAuthorizationRow(Base):
    __tablename__ = "ai_egress_authorizations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"],
            name="fk_ai_egress_authorizations__preview", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_ai_egress_authorizations__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["approved_by"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authorizations__approver", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["ai_model_id"], ["plm.ai_models.ai_model_id"],
            name="fk_ai_egress_authorizations__model", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_egress_authorizations__provider_config", ondelete="NO ACTION",
        ),
        UniqueConstraint("egress_preview_id", name="uq_ai_egress_authorizations__preview"),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL AND approved_role='DeploymentAdmin') OR "
            "(scope='PROJECT' AND project_id IS NOT NULL "
            "AND approved_role IN ('ProjectManager','CustomerManager'))",
            name="ck_ai_egress_authorizations__scope_role",
        ),
        CheckConstraint(
            "authorization_state IN ('AUTHORIZED','REVOKED') AND lock_version BETWEEN 0 AND 1",
            name="ck_ai_egress_authorizations__state",
        ),
        CheckConstraint(
            "purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND minimal_payload_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND data_region ~ '^[a-z][a-z0-9-]{0,63}$' "
            "AND operation_type IN ('AI_TASK','RETRIEVAL_RUN','INDEX_BUILD','INDEX_REBUILD')",
            name="ck_ai_egress_authorizations__refs",
        ),
        CheckConstraint(
            "jsonb_typeof(allowed_data_categories)='array' "
            "AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64",
            name="ck_ai_egress_authorizations__categories",
        ),
        CheckConstraint(
            "max_record_count BETWEEN 0 AND 1000000000 "
            "AND max_payload_bytes BETWEEN 1 AND 1073741824 "
            "AND max_input_tokens BETWEEN 1 AND 1048576 "
            "AND max_retry_attempts BETWEEN 1 AND 10",
            name="ck_ai_egress_authorizations__bounds",
        ),
        CheckConstraint(
            "octet_length(payload_fingerprint)=32 AND octet_length(source_refs_fingerprint)=32",
            name="ck_ai_egress_authorizations__fingerprints",
        ),
        CheckConstraint(
            "authorization_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND egress_preview_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND approved_by<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_egress_authorizations__uuid",
        ),
        CheckConstraint(
            "approved_at<valid_until AND isfinite(approved_at) AND isfinite(valid_until) "
            "AND created_xid>0",
            name="ck_ai_egress_authorizations__time",
        ),
        Index(
            "ix_ai_egress_authorizations__project_state_expiry",
            "project_id", "authorization_state", "valid_until", "authorization_id",
        ),
    )

    authorization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    egress_preview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purpose_ref: Mapped[str] = mapped_column(Text, nullable=False)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_region: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    minimal_payload_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    max_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_payload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_refs_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    authorization_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'AUTHORIZED'"),
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approved_role: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    valid_until: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class AIEgressAuthorizationRevocationRow(Base):
    __tablename__ = "ai_egress_authorization_revocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_authz_revocations__authorization", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["revoked_by"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authz_revocations__actor", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_authz_revocations__audit", ondelete="NO ACTION",
        ),
        UniqueConstraint("authorization_id", name="uq_ai_egress_authz_revocations__authorization"),
        UniqueConstraint("audit_event_id", name="uq_ai_egress_authz_revocations__audit"),
        CheckConstraint(
            "revocation_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND authorization_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND revoked_by<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND revoked_role IN ('OriginalApprover','DeploymentAdmin','ProjectManager','CustomerManager') "
            "AND reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$' "
            "AND char_length(reason_summary) BETWEEN 1 AND 2000 "
            "AND char_length(btrim(reason_summary))>0 "
            "AND isfinite(revoked_at) AND created_xid>0",
            name="ck_ai_egress_authz_revocations__shape",
        ),
    )

    revocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    authorization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_role: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class AIEgressAuthorizeResultRow(Base):
    __tablename__ = "ai_egress_authorize_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_authorize_results__authorization", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"],
            name="fk_ai_egress_authorize_results__preview", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["actor_id"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authorize_results__actor", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_authorize_results__audit", ondelete="NO ACTION",
        ),
        UniqueConstraint("authorization_id", name="uq_ai_egress_authorize_results__authorization"),
        UniqueConstraint("egress_preview_id", name="uq_ai_egress_authorize_results__preview"),
        UniqueConstraint("audit_event_id", name="uq_ai_egress_authorize_results__audit"),
        CheckConstraint(
            "result_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND authorization_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND egress_preview_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND approved_role IN ('DeploymentAdmin','ProjectManager','CustomerManager') "
            "AND result_state='AUTHORIZED' AND lock_version=0 "
            "AND approved_at<valid_until AND isfinite(approved_at) AND isfinite(valid_until) "
            "AND created_xid>0",
            name="ck_ai_egress_authorize_results__shape",
        ),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    authorization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    egress_preview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approved_role: Mapped[str] = mapped_column(Text, nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    result_state: Mapped[str] = mapped_column(Text, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class AIEgressRevokeResultRow(Base):
    __tablename__ = "ai_egress_revoke_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_revoke_results__authorization", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["revocation_id"], ["plm.ai_egress_authorization_revocations.revocation_id"],
            name="fk_ai_egress_revoke_results__revocation", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["actor_id"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_revoke_results__actor", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_revoke_results__audit", ondelete="NO ACTION",
        ),
        UniqueConstraint("authorization_id", name="uq_ai_egress_revoke_results__authorization"),
        UniqueConstraint("revocation_id", name="uq_ai_egress_revoke_results__revocation"),
        UniqueConstraint("audit_event_id", name="uq_ai_egress_revoke_results__audit"),
        CheckConstraint(
            "result_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND authorization_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND revocation_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND revoked_role IN ('OriginalApprover','DeploymentAdmin','ProjectManager','CustomerManager') "
            "AND result_state='REVOKED' AND lock_version=1 "
            "AND isfinite(revoked_at) AND created_xid>0",
            name="ck_ai_egress_revoke_results__shape",
        ),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    authorization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revocation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_role: Mapped[str] = mapped_column(Text, nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    result_state: Mapped[str] = mapped_column(Text, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )
