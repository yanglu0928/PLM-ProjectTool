"""Caller-owned capture transaction. MUST NOT be exposed without real auth.

Actor/Scope binding is NOT permission. Caller must first authorize actual current
facts and hold their locks, License/lease checks, then commit or roll back the
whole UOW. No Session/token, implicit UOW, commit, rollback or auth fallback here.
"""
from sqlalchemy import insert, select, text
from ..application.capture_contract import AuditCaptureError, CapturedAuditExport
from ..application.export_contract import (
    AuditExportAuthorityRequest, AuditExportSpec, EXPORT_FORMAT,
    EXPORT_POLICY_VERSION, EXPORT_PROJECTION_VERSION,
)
from ..domain.capture_membership import MEMBERSHIP_VERSION
from .audit_read_repository import _session
from .export_orm import exports, captures

CAPTURE_ROW_LIMIT = 100_000  # Versioned server policy; not client configuration.
_MATCH = """e.event_scope=r.scope AND e.target_project_id IS NOT DISTINCT FROM r.project_id
    AND e.occurred_at>=r.start_at AND e.occurred_at<r.end_at
    AND (r.action IS NULL OR e.action=r.action)
    AND (r.outcome IS NULL OR e.outcome=r.outcome)
    AND (r.filter_actor_id IS NULL OR e.actor_id=r.filter_actor_id)
    AND (r.target_object_type IS NULL OR e.target_object_type=r.target_object_type)
    AND (r.target_object_id IS NULL OR e.target_object_id=r.target_object_id)
    AND (r.filter_trace_id IS NULL OR e.trace_id=r.filter_trace_id)"""
_CAPTURE = text("""
    WITH chosen AS (
        SELECT e.audit_event_id,e.occurred_at,
            row_number() OVER(ORDER BY e.occurred_at DESC,e.audit_event_id DESC) AS position
        FROM plm.aud_events e JOIN plm.aud_exports r ON r.export_id=:export_id
        WHERE """+_MATCH+"""
        ORDER BY e.occurred_at DESC,e.audit_event_id DESC LIMIT :row_limit
    ), written AS (
        INSERT INTO plm.aud_export_members(export_id,position,event_id,occurred_at)
        SELECT :export_id,position,audit_event_id,occurred_at FROM chosen
        RETURNING position
    ) SELECT statement_timestamp() AS captured_at,count(*) AS member_count FROM written
""")
_STATS = text("""
    SELECT count(*) AS member_count,
        coalesce(bool_or(m.position<>m.rank OR e.audit_event_id IS NULL
            OR e.occurred_at IS DISTINCT FROM m.occurred_at OR NOT("""+_MATCH+""")),false) AS invalid,
        count(DISTINCT m.created_xid) AS xid_count,min(m.created_xid) AS created_xid,
        encode(sha256(convert_to('PLM-AUDIT-CAPTURE-MEMBERSHIP-V1','UTF8')||decode('00','hex')||
            convert_to(coalesce(string_agg(m.event_id::text||'|'||
                to_char(m.occurred_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')||chr(10),'' ORDER BY m.position),''),'UTF8')),'hex') AS membership_hash
    FROM (SELECT *,row_number() OVER(ORDER BY occurred_at DESC,event_id DESC) AS rank
        FROM plm.aud_export_members WHERE export_id=:export_id) m
    LEFT JOIN plm.aud_events e ON e.audit_event_id=m.event_id
    JOIN plm.aud_exports r ON r.export_id=m.export_id
""")


class SqlAlchemyAuditCaptureRepository:
    def _root(self, transaction, request):
        if type(request) is not AuditExportAuthorityRequest:
            raise AuditCaptureError("INVALID_REQUEST")
        try:
            request.__post_init__()
        except ValueError as exc:
            raise AuditCaptureError("INVALID_REQUEST") from exc
        session = _session(transaction)
        connection = session.connection()
        if connection.dialect.name != "postgresql" or connection.get_isolation_level() != "READ COMMITTED":
            raise AuditCaptureError("INVALID_REQUEST")
        row = session.execute(select(exports).where(exports.c.export_id==request.export_id)
            .with_for_update()).mappings().one_or_none()
        if row is None:
            raise AuditCaptureError("NOT_FOUND")
        if (row["actor_id"],row["scope"],row["project_id"]) != (request.actor_id,request.scope,request.project_id):
            raise AuditCaptureError("BINDING_MISMATCH")
        try:
            spec = AuditExportSpec(row["scope"],row["project_id"],row["purpose"],row["start_at"],row["end_at"],
                action=row["action"],outcome=row["outcome"],actor_id=row["filter_actor_id"],
                target_object_type=row["target_object_type"],target_object_id=row["target_object_id"],trace_id=row["filter_trace_id"])
            if ((row["policy_version"],row["projection_version"],row["format_version"])
                    != (EXPORT_POLICY_VERSION,EXPORT_PROJECTION_VERSION,EXPORT_FORMAT)
                    or spec.fingerprint()!=row["intent_hash"]):
                raise ValueError("invalid Audit intent")
        except (ValueError,TypeError) as exc:
            raise AuditCaptureError() from exc
        return session,row

    def _existing(self, session, root):
        seal = session.execute(select(captures).where(captures.c.export_id==root["export_id"])).mappings().one_or_none()
        if seal is None:
            return None
        stats = session.execute(_STATS,dict(export_id=root["export_id"])).mappings().one()
        if (seal["membership_version"]!=MEMBERSHIP_VERSION or seal["captured_at"]<root["requested_at"]
                or stats["invalid"] or stats["member_count"]!=seal["member_count"]
                or seal["member_count"]>CAPTURE_ROW_LIMIT or stats["membership_hash"]!=seal["membership_hash"]
                or (stats["member_count"]>0 and (stats["xid_count"]!=1 or stats["created_xid"]!=seal["created_xid"]))):
            raise AuditCaptureError()
        return CapturedAuditExport(root["export_id"],root["actor_id"],root["scope"],root["project_id"],
            root["requested_at"],seal["captured_at"],seal["member_count"],seal["membership_hash"],
            seal["membership_version"],root["intent_hash"],root["policy_version"],root["projection_version"],root["format_version"])

    def capture(self, transaction, *, request):
        if type(request) is not AuditExportAuthorityRequest or request.stage!="CAPTURE":
            raise AuditCaptureError("INVALID_REQUEST")
        session,root = self._root(transaction,request)
        existing = self._existing(session,root)
        if existing is not None:
            return existing  # Never requery live source membership on replay.
        result = session.execute(_CAPTURE,dict(export_id=request.export_id,row_limit=CAPTURE_ROW_LIMIT+1)).mappings().one()
        if result["member_count"]>CAPTURE_ROW_LIMIT:
            raise AuditCaptureError("LIMIT_EXCEEDED")  # Caller must roll back, never seal truncation.
        stats = session.execute(_STATS,dict(export_id=request.export_id)).mappings().one()
        if stats["invalid"] or stats["member_count"]!=result["member_count"]:
            raise AuditCaptureError()
        session.execute(insert(captures).values(export_id=request.export_id,captured_at=result["captured_at"],
            member_count=result["member_count"],membership_hash=stats["membership_hash"],membership_version=MEMBERSHIP_VERSION))
        return self._existing(session,root)

    def read_capture(self, transaction, *, request):
        """Trusted caller must reauthorize current facts before this result lookup."""
        session,root = self._root(transaction,request)
        return self._existing(session,root)
