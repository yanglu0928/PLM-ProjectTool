"""Internal immutable result contracts; never file presence or authority permits."""
from dataclasses import dataclass
from datetime import datetime,timedelta
import hashlib
from re import fullmatch
from typing import Protocol
from uuid import UUID
from .render_plan import AuditRenderPlan
from .render_export import RenderedAuditExport,MAX_EXPORT_BYTES,MAX_MANIFEST_BYTES,MANIFEST_VERSION


class AuditExportResultError(RuntimeError):
    def __init__(self):super().__init__('AUDIT_UNAVAILABLE')


def _uuid(value):return type(value) is UUID and bool(value.int)


@dataclass(frozen=True,slots=True)
class RecordAuditExportResult:
    plan: AuditRenderPlan
    rendered: RenderedAuditExport
    publish_audit_event_id: UUID

    def __post_init__(self):
        if type(self.plan) is not AuditRenderPlan or type(self.rendered) is not RenderedAuditExport or not _uuid(self.publish_audit_event_id):
            raise AuditExportResultError()
        self.plan.__post_init__()
        r=self.rendered
        if (not _uuid(r.export_id) or r.export_id!=self.plan.export_id
                or type(r.member_count) is not int or r.member_count!=self.plan.member_count
                or type(r.byte_count) is not int or not 0<=r.byte_count<=MAX_EXPORT_BYTES
                or type(r.file_sha256) is not str or not fullmatch(r'[0-9a-f]{64}',r.file_sha256)
                or type(r.manifest_bytes) is not bytes or not 1<=len(r.manifest_bytes)<=MAX_MANIFEST_BYTES):
            raise AuditExportResultError()


@dataclass(frozen=True,slots=True)
class AuditExportResult:
    export_id: UUID
    render_attempt_id: UUID
    file_id: UUID
    file_sha256: bytes
    byte_count: int
    mime_type: str
    manifest_version: str
    manifest_bytes: bytes
    manifest_sha256: bytes
    publish_audit_event_id: UUID
    published_at: datetime

    def __post_init__(self):
        if (not all(_uuid(v) for v in (self.export_id,self.render_attempt_id,self.file_id,self.publish_audit_event_id))
                or type(self.file_sha256) is not bytes or len(self.file_sha256)!=32
                or type(self.byte_count) is not int or not 0<=self.byte_count<=MAX_EXPORT_BYTES
                or type(self.mime_type) is not str or self.mime_type!='application/x-ndjson'
                or type(self.manifest_version) is not str or self.manifest_version!=MANIFEST_VERSION
                or type(self.manifest_bytes) is not bytes or not 1<=len(self.manifest_bytes)<=MAX_MANIFEST_BYTES
                or type(self.manifest_sha256) is not bytes or self.manifest_sha256!=hashlib.sha256(self.manifest_bytes).digest()
                or type(self.published_at) is not datetime or self.published_at.tzinfo is None
                or self.published_at.utcoffset()!=timedelta(0)):
            raise AuditExportResultError()


@dataclass(frozen=True,slots=True)
class AuditExportResultMutation:
    result: AuditExportResult
    changed: bool

    def __post_init__(self):
        if type(self.result) is not AuditExportResult or type(self.changed) is not bool:raise AuditExportResultError()
        self.result.__post_init__()


class AuditExportResultRepositoryPort(Protocol):
    def record(self,tx:object,*,request:RecordAuditExportResult)->AuditExportResultMutation: ...
    def get(self,tx:object,*,export_id:UUID)->AuditExportResult|None: ...
