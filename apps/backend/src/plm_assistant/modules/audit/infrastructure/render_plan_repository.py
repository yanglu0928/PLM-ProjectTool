"""Audit owned, caller-UOW repository; no authority, file I/O or commit."""
from sqlalchemy import select,text
from datetime import timezone
from uuid import UUID
from sqlalchemy.dialects.postgresql import insert
from .audit_read_repository import _session
from .export_orm import render_attempts
from ..application.render_plan import AuditRenderPlan
from ..application.worker_capture import AuditExportWorkerError
from ..application.submit_export import AuditExportIntent
from ..application.capture_contract import CapturedAuditExport
from ..application.worker_capture import AuditExportWorkerCapture
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class SqlAlchemyAuditRenderPlans:
    def find(self,tx,*,export_id,job_id,fencing_token):
        if (any(type(v) is not UUID or not v.int for v in (export_id,job_id))
                or type(fencing_token) is not int or not 0<fencing_token<2**63):raise AuditExportWorkerError()
        row=_session(tx).execute(select(render_attempts).where(render_attempts.c.export_id==export_id,
            render_attempts.c.job_id==job_id,render_attempts.c.fencing_token==fencing_token)).mappings().one_or_none()
        if row is None:return None
        source=dict(row);source['created_at']=source['created_at'].astimezone(timezone.utc)
        return AuditRenderPlan(**source)

    def register(self,tx,*,intent,capture,claim,worker_ref):
        if (type(intent) is not AuditExportIntent or type(capture) is not CapturedAuditExport
                or type(claim) is not ClaimedJob):raise AuditExportWorkerError()
        intent.__post_init__()
        AuditExportWorkerCapture._result(capture,intent)
        session=_session(tx)
        # PostgreSQL allocates UUIDs; never accept a client-selected file path or ID.
        values=dict(export_id=intent.export_id,job_id=claim.job_id,fencing_token=claim.fencing_token,
            attempt_no=claim.attempt_no,worker_ref=worker_ref,file_id=text('uuidv7()'),
            member_count=capture.member_count,membership_hash=capture.membership_hash,
            membership_version=capture.membership_version)
        session.execute(insert(render_attempts).values(**values).on_conflict_do_nothing(
            constraint="uq_aud_render_attempts__job_fence"))
        row=session.execute(select(render_attempts).where(render_attempts.c.job_id==claim.job_id,
            render_attempts.c.fencing_token==claim.fencing_token).with_for_update()).mappings().one()
        source=dict(row)
        source['created_at']=source['created_at'].astimezone(timezone.utc)
        result=AuditRenderPlan(**source)
        if ((result.export_id,result.attempt_no,result.worker_ref,result.member_count,
             result.membership_hash,result.membership_version)
                !=(intent.export_id,claim.attempt_no,worker_ref,capture.member_count,
                   capture.membership_hash,capture.membership_version)
                or result.created_at<capture.captured_at):raise AuditExportWorkerError()
        return result
