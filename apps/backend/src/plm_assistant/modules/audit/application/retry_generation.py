"""Immutable first generation receipt; coordinates are NOT retry authority."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True, slots=True)
class AuditExportRetryGeneration:
    new_export_id: UUID
    source_export_id: UUID
    source_job_id: UUID
    source_failure_event_id: UUID
    new_job_id: UUID
    new_event_id: UUID
    retry_audit_event_id: UUID
    expected_source_version: int
    first_job_version: int
    created_at: datetime

    def __post_init__(self):
        ids=(self.new_export_id,self.source_export_id,self.source_job_id,self.source_failure_event_id,
            self.new_job_id,self.new_event_id,self.retry_audit_event_id)
        if (any(type(v) is not UUID or not v.int for v in ids)
            or self.new_export_id==self.source_export_id or self.new_job_id==self.source_job_id
            or type(self.expected_source_version) is not int or not 0<=self.expected_source_version<=9223372036854775807
            or type(self.first_job_version) is not int or self.first_job_version!=0
            or type(self.created_at) is not datetime or self.created_at.tzinfo is None or self.created_at.utcoffset() is None):
            raise ValueError('Invalid Audit retry generation')
