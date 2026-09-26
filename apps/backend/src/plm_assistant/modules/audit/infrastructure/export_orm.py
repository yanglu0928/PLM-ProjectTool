"""Audit owned immutable export/capture rows; not authorized commands."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from plm_assistant.modules.platform.infrastructure.orm import Base

_id = UUID(as_uuid=True)
_time = TIMESTAMP(timezone=True, precision=6)
_zero = "'00000000-0000-0000-0000-000000000000'::uuid"


def _col(name, kind=sa.Text(), nullable=False, **kw):
    return sa.Column(name, kind, nullable=nullable, **kw)


exports = sa.Table("aud_exports", Base.metadata,
    _col("export_id", _id, primary_key=True, server_default=sa.text("uuidv7()")),
    _col("actor_id", _id), _col("scope"), _col("project_id", _id, nullable=True),
    _col("trace_id", _id), _col("requested_at", _time, server_default=sa.text("statement_timestamp()")),
    _col("purpose"), _col("start_at", _time), _col("end_at", _time),
    _col("action", nullable=True), _col("outcome", nullable=True),
    _col("filter_actor_id", _id, nullable=True), _col("target_object_type", nullable=True),
    _col("target_object_id", _id, nullable=True), _col("filter_trace_id", _id, nullable=True),
    _col("policy_version"), _col("projection_version"), _col("format_version"), _col("intent_hash"),
    sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"], name="fk_aud_exports__actor_id__auth_users"),
    sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_aud_exports__project_id__prj_projects"),
    sa.CheckConstraint("(scope='DEPLOYMENT' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL AND project_id<>"+_zero+")", name="ck_aud_exports__scope"),
    sa.CheckConstraint("purpose IN ('SECURITY_REVIEW','COMPLIANCE_REVIEW','PROJECT_GOVERNANCE','INCIDENT_INVESTIGATION') AND NOT(scope='DEPLOYMENT' AND purpose='PROJECT_GOVERNANCE')", name="ck_aud_exports__purpose"),
    sa.CheckConstraint("start_at>=timestamptz '0001-01-01 00:00:00+00' AND end_at<timestamptz '10000-01-01 00:00:00+00' AND start_at<end_at AND end_at-start_at<=interval '31 days' AND isfinite(requested_at)", name="ck_aud_exports__window"),
    sa.CheckConstraint("(action IS NULL OR action ~ '^[A-Z][A-Z0-9_]{0,63}$') AND (outcome IS NULL OR outcome IN ('SUCCESS','DENIED','FAILED')) AND (target_object_type IS NULL OR target_object_type ~ '^[A-Z]{2,3}-[0-9]{2}$')", name="ck_aud_exports__filters"),
    sa.CheckConstraint("policy_version='AUDIT-EXPORT-POLICY-V1' AND projection_version='AUDIT-EVENT-SAFE-V1' AND format_version='JSONL_V1' AND intent_hash ~ '^[0-9a-f]{64}$'", name="ck_aud_exports__versions"),
    sa.CheckConstraint(" AND ".join(c+"<>"+_zero for c in ("export_id", "actor_id", "trace_id"))+" AND "+" AND ".join("("+c+" IS NULL OR "+c+"<>"+_zero+")" for c in ("filter_actor_id", "target_object_id", "filter_trace_id")), name="ck_aud_exports__uuid"),
    sa.PrimaryKeyConstraint("export_id", name="pk_aud_exports"),
)
members = sa.Table("aud_export_members", Base.metadata,
    _col("export_id", _id), _col("position", sa.BigInteger()), _col("event_id", _id),
    _col("occurred_at", _time), _col("created_xid", sa.BigInteger(), server_default=sa.text("txid_current()")),
    sa.PrimaryKeyConstraint("export_id", "position", name="pk_aud_export_members"),
    sa.UniqueConstraint("export_id", "event_id", name="uq_aud_export_members__export_id_event_id"),
    sa.ForeignKeyConstraint(["export_id"], ["plm.aud_exports.export_id"], name="fk_aud_export_members__export_id__aud_exports"),
    sa.ForeignKeyConstraint(["event_id"], ["plm.aud_events.audit_event_id"], name="fk_aud_export_members__event_id__aud_events"),
    sa.CheckConstraint("position>=1", name="ck_aud_export_members__position"),
)
captures = sa.Table("aud_export_captures", Base.metadata,
    _col("export_id", _id, primary_key=True),
    _col("captured_at", _time, server_default=sa.text("statement_timestamp()")),
    _col("member_count", sa.BigInteger()), _col("membership_hash"), _col("membership_version"),
    _col("created_xid", sa.BigInteger(), server_default=sa.text("txid_current()")),
    sa.PrimaryKeyConstraint("export_id", name="pk_aud_export_captures"),
    sa.ForeignKeyConstraint(["export_id"], ["plm.aud_exports.export_id"], name="fk_aud_export_captures__export_id__aud_exports"),
    sa.CheckConstraint("member_count>=0 AND membership_hash ~ '^[0-9a-f]{64}$' AND membership_version='CAPTURE-MEMBERSHIP-V1' AND isfinite(captured_at)", name="ck_aud_export_captures__shape"),
)


class AuditExportRow(Base):
    __table__ = exports


class AuditExportMemberRow(Base):
    __table__ = members


class AuditExportCaptureRow(Base):
    __table__ = captures


acceptances = sa.Table("aud_export_acceptances", Base.metadata,
    _col("export_id", _id, primary_key=True), _col("job_id", _id), _col("event_id", _id),
    _col("request_audit_event_id", _id),
    _col("accepted_at", _time, server_default=sa.text("statement_timestamp()")),
    sa.ForeignKeyConstraint(["export_id"], ["plm.aud_exports.export_id"], name="fk_aud_export_acceptances__export_id__aud_exports"),
    sa.ForeignKeyConstraint(["request_audit_event_id"], ["plm.aud_events.audit_event_id"], name="fk_aud_export_acceptances__audit_event__aud_events"),
    sa.UniqueConstraint("job_id", name="uq_aud_export_acceptances__job_id"),
    sa.UniqueConstraint("event_id", name="uq_aud_export_acceptances__event_id"),
    sa.UniqueConstraint("request_audit_event_id", name="uq_aud_export_acceptances__request_audit_event_id"),
    sa.CheckConstraint("isfinite(accepted_at) AND "+" AND ".join(c+"<>"+_zero for c in ("export_id","job_id","event_id","request_audit_event_id")), name="ck_aud_export_acceptances__shape"),
)


class AuditExportAcceptanceRow(Base):
    __table__ = acceptances


render_attempts = sa.Table("aud_export_render_attempts", Base.metadata,
    _col("render_attempt_id", _id, primary_key=True, server_default=sa.text("uuidv7()")),
    _col("export_id", _id), _col("job_id", _id), _col("fencing_token", sa.BigInteger()),
    _col("attempt_no", sa.Integer()), _col("worker_ref"), _col("file_id", _id),
    _col("member_count", sa.BigInteger()), _col("membership_hash"), _col("membership_version"),
    _col("created_at", _time, server_default=sa.text("statement_timestamp()")),
    sa.PrimaryKeyConstraint("render_attempt_id", name="pk_aud_export_render_attempts"),
    sa.ForeignKeyConstraint(["export_id"], ["plm.aud_export_captures.export_id"], name="fk_aud_render_attempts__capture"),
    sa.ForeignKeyConstraint(["export_id"], ["plm.aud_export_acceptances.export_id"], name="fk_aud_render_attempts__acceptance"),
    sa.UniqueConstraint("job_id", "fencing_token", name="uq_aud_render_attempts__job_fence"),
    sa.UniqueConstraint("file_id", name="uq_aud_render_attempts__file"),
    sa.CheckConstraint("""render_attempt_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND export_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND job_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND file_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND fencing_token>0 AND attempt_no>0 AND member_count BETWEEN 0 AND 100000
 AND worker_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
 AND membership_hash ~ '^[0-9a-f]{64}$'
 AND membership_version='CAPTURE-MEMBERSHIP-V1' AND isfinite(created_at)""", name="ck_aud_render_attempts__shape"),
    sa.Index("ix_aud_render_attempts__export_created", "export_id", "created_at"),
)


class AuditExportRenderAttemptRow(Base):
    __table__ = render_attempts
