"""Bounded canonical safe JSONL and manifest; NOT current authority or publication."""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
from re import fullmatch
from typing import Iterable,Protocol
from uuid import UUID
from .submit_export import AuditExportIntent
from .capture_contract import CapturedAuditExport
from .queries.audit_query import AuditEventView
from .public import AuditEventDraft
from ..domain.capture_membership import CaptureMember,digest_members,MEMBERSHIP_VERSION

MAX_EXPORT_BYTES=128*1024*1024
MAX_LINE_BYTES=16*1024
MAX_MANIFEST_BYTES=8192
MANIFEST_VERSION="AUDIT-EXPORT-MANIFEST-V1"
_FIELDS=("audit_event_id","occurred_at","trace_id","event_scope","target_project_id","actor_type","actor_id",
    "original_actor_id","action","outcome","target_owner_module","target_object_type","target_object_id",
    "target_version_id","reason_code","before_state","after_state")


class AuditExportRenderError(RuntimeError):
    def __init__(self,code="AUDIT_EXPORT_RENDER_FAILED"):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditExportRenderItem:
    position: int
    event: AuditEventView


@dataclass(frozen=True,slots=True)
class RenderedAuditExport:
    export_id: UUID
    byte_count: int
    file_sha256: str
    member_count: int
    manifest_bytes: bytes


class AuditExportRenderSourcePort(Protocol):
    def iter_events(self,transaction:object,*,export_id:UUID)->Iterable[AuditExportRenderItem]: ...


class AuditExportRenderPagePort(Protocol):
    def read_page(self,transaction:object,*,export_id:UUID,after_position:int,page_size:int)->tuple[AuditExportRenderItem,...]: ...


def _stamp(value):return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
def _json(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")+b"\n"
def _encode(value):
    if type(value) is UUID:return str(value)
    if type(value) is datetime:return _stamp(value)
    return value


class AuditExportRenderer:
    def render(self,*,intent:AuditExportIntent,capture:CapturedAuditExport,items:Iterable[AuditExportRenderItem],sink)->RenderedAuditExport:
        """Caller must keep partial bytes private on EVERY failure. No success without full digest."""
        try:return self._render(intent,capture,items,sink)
        except AuditExportRenderError:raise
        except Exception:raise AuditExportRenderError() from None

    @staticmethod
    def _bound(intent,capture):
        if type(intent) is not AuditExportIntent or type(capture) is not CapturedAuditExport:raise AuditExportRenderError()
        intent.__post_init__()
        if ((capture.export_id,capture.actor_id,capture.scope,capture.project_id,capture.requested_at,capture.intent_hash,
             capture.policy_version,capture.projection_version,capture.format_version)
            !=(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.requested_at,intent.intent_hash,
               intent.policy_version,intent.projection_version,intent.format_version)
            or type(capture.member_count) is not int or not 0<=capture.member_count<=100000
            or capture.membership_version!=MEMBERSHIP_VERSION or type(capture.membership_hash) is not str
            or not fullmatch(r"[0-9a-f]{64}",capture.membership_hash)
            or type(capture.captured_at) is not datetime or capture.captured_at.tzinfo is None
            or capture.captured_at.utcoffset() is None or capture.captured_at<intent.requested_at):raise AuditExportRenderError()

    @staticmethod
    def _event(item,index,intent):
        if type(item) is not AuditExportRenderItem or type(item.position) is not int or item.position!=index:
            raise AuditExportRenderError()
        view=item.event;spec=intent.spec
        if type(view) is not AuditEventView:raise AuditExportRenderError()
        CaptureMember(view.audit_event_id,view.occurred_at).__post_init__()
        if ((view.event_scope,view.target_project_id)!=(spec.scope,spec.project_id)
                or not spec.start_at<=view.occurred_at<spec.end_at):raise AuditExportRenderError()
        for expected,actual in ((spec.action,view.action),(spec.outcome,view.outcome),(spec.actor_id,view.actor_id),
                (spec.target_object_type,view.target_object_type),(spec.target_object_id,view.target_object_id),(spec.trace_id,view.trace_id)):
            if expected is not None and expected!=actual:raise AuditExportRenderError()
        # Reuse owned code/actor/typed-ref validation, but never copy private ORM attributes.
        AuditEventDraft(**{field:getattr(view,field) for field in _FIELDS if field not in {"audit_event_id","occurred_at"}},actor_hint_digest=None)
        return view

    def _render(self,intent,capture,items,sink):
        self._bound(intent,capture)
        if not callable(getattr(sink,"write",None)):raise AuditExportRenderError()
        stream=iter(items)
        digest=hashlib.sha256();byte_count=0
        def members():
            nonlocal byte_count
            for index,item in enumerate(stream,1):
                if index>capture.member_count:raise AuditExportRenderError()
                view=self._event(item,index,intent)
                line=_json({field:_encode(getattr(view,field)) for field in _FIELDS})
                if len(line)>MAX_LINE_BYTES or byte_count+len(line)>MAX_EXPORT_BYTES:
                    raise AuditExportRenderError("AUDIT_EXPORT_SIZE_EXCEEDED")
                written=sink.write(line)
                if type(written) is not int or written!=len(line):raise AuditExportRenderError()
                digest.update(line);byte_count+=written
                yield CaptureMember(view.audit_event_id,view.occurred_at)
        try:membership=digest_members(members())
        finally:
            close=getattr(stream,"close",None)
            if callable(close):close()
        if membership.count!=capture.member_count or membership.sha256!=capture.membership_hash:raise AuditExportRenderError()
        manifest=build_audit_export_manifest(intent,capture,file_sha256=digest.hexdigest(),byte_count=byte_count)
        return RenderedAuditExport(intent.export_id,byte_count,digest.hexdigest(),membership.count,manifest)


def build_audit_export_manifest(intent,capture,*,file_sha256,byte_count):
    """Bounded safe canonical metadata only. Does not prove these bytes exist on disk."""
    AuditExportRenderer._bound(intent,capture)
    if (type(file_sha256) is not str or not fullmatch(r"[0-9a-f]{64}",file_sha256)
            or type(byte_count) is not int or not 0<=byte_count<=MAX_EXPORT_BYTES
            or (capture.member_count==0 and (byte_count!=0 or file_sha256!=hashlib.sha256(b'').hexdigest()))
            or (capture.member_count>0 and byte_count<capture.member_count)):
        raise AuditExportRenderError()
    spec=intent.spec
    manifest=dict(manifest_version=MANIFEST_VERSION,export_id=str(intent.export_id),actor_id=str(intent.actor_id),scope=spec.scope,project_id=_encode(spec.project_id),purpose=spec.purpose,
        requested_at=_stamp(intent.requested_at),captured_at=_stamp(capture.captured_at),start_at=_stamp(spec.start_at),end_at=_stamp(spec.end_at),
        filters=dict(action=spec.action,outcome=spec.outcome,actor_id=_encode(spec.actor_id),target_object_type=spec.target_object_type,
            target_object_id=_encode(spec.target_object_id),trace_id=_encode(spec.trace_id)),intent_hash=intent.intent_hash,
        policy_version=intent.policy_version,projection_version=intent.projection_version,format_version=intent.format_version,
        membership_version=capture.membership_version,member_count=capture.member_count,membership_sha256=capture.membership_hash,
        file_sha256=file_sha256,byte_count=byte_count)
    encoded=_json(manifest)
    if len(encoded)>MAX_MANIFEST_BYTES:raise AuditExportRenderError()
    return encoded
