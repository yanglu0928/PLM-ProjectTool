"""Trusted caller-UOW metadata; caller supplies actual authority, bytes and Audit."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID
from .audit_export_storage import AuditFileContent


class AuditFileMetadataError(RuntimeError):
    def __init__(self, code="FILE_UNAVAILABLE"):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class RegisterAuditFile:
    export_id: UUID
    actor_id: UUID
    trace_id: UUID
    content: AuditFileContent

    def __post_init__(self):
        if any(type(value) is not UUID or not value.int for value in (self.export_id,self.actor_id,self.trace_id)):
            raise AuditFileMetadataError()
        if type(self.content) is not AuditFileContent:
            raise AuditFileMetadataError()
        try:self.content.__post_init__()
        except Exception:raise AuditFileMetadataError() from None


@dataclass(frozen=True,slots=True)
class AuditFileMetadata:
    content: AuditFileContent
    export_id: UUID
    actor_id: UUID
    registration_trace_id: UUID
    registration_event_id: UUID
    state: str
    lock_version: int
    created_at: datetime
    available_at: datetime | None
    available_event_id: UUID | None

    def __post_init__(self):
        RegisterAuditFile(self.export_id,self.actor_id,self.registration_trace_id,self.content)
        if (type(self.registration_event_id) is not UUID or not self.registration_event_id.int
                or type(self.state) is not str or self.state not in ("STAGED","AVAILABLE","RESTRICTED")
                or type(self.lock_version) is not int or self.lock_version!={"STAGED":0,"AVAILABLE":1,"RESTRICTED":2}[self.state]
                or type(self.created_at) is not datetime or self.created_at.tzinfo is None or self.created_at.utcoffset() is None):
            raise AuditFileMetadataError()
        if self.state=="STAGED":
            if self.available_at is not None or self.available_event_id is not None:raise AuditFileMetadataError()
        elif (type(self.available_at) is not datetime or self.available_at.tzinfo is None or self.available_at.utcoffset() is None
                or self.available_at<self.created_at or type(self.available_event_id) is not UUID or not self.available_event_id.int):
            raise AuditFileMetadataError()


@dataclass(frozen=True,slots=True)
class AuditFileMutation:
    metadata: AuditFileMetadata
    changed: bool

    def __post_init__(self):
        if type(self.metadata) is not AuditFileMetadata or type(self.changed) is not bool:raise AuditFileMetadataError()
        self.metadata.__post_init__()


class AuditExportFileMetadataPort(Protocol):
    def register_staged(self, transaction:object, *, request:RegisterAuditFile)->AuditFileMutation: ...
    def get(self, transaction:object, *, request:RegisterAuditFile)->AuditFileMetadata: ...
    def mark_available(self, transaction:object, *, request:RegisterAuditFile, expected_version:int)->AuditFileMutation: ...
