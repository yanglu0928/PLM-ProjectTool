"""Audit-owned immutable first response, no Job table access or own commit."""
from sqlalchemy import select, insert
from .audit_read_repository import _session
from .export_orm import retry_generations
from ..application.retry_generation import AuditExportRetryGeneration

class SqlAlchemyAuditRetryGenerations:
    def get(self,tx,*,new_export_id):
        row=_session(tx).execute(select(retry_generations).where(retry_generations.c.new_export_id==new_export_id)).mappings().one_or_none()
        return None if row is None else AuditExportRetryGeneration(**dict(row))

    def record(self,tx,*,source,new_accepted,retry_audit_event_id):
        value=dict(new_export_id=new_accepted.intent.export_id,source_export_id=source.accepted.intent.export_id,
            source_job_id=source.accepted.job_id,source_failure_event_id=source.failure_event_id,
            new_job_id=new_accepted.job_id,new_event_id=new_accepted.event_id,retry_audit_event_id=retry_audit_event_id,
            expected_source_version=source.failure.lock_version,first_job_version=0)
        row=_session(tx).execute(insert(retry_generations).values(**value).returning(retry_generations)).mappings().one()
        return AuditExportRetryGeneration(**dict(row))
