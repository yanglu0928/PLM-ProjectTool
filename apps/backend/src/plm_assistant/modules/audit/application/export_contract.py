"""Fixed export intent and real-current-authority Port, never permission proof."""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
from typing import Protocol
from uuid import UUID
from .queries.audit_query import AuditSearch

EXPORT_POLICY_VERSION="AUDIT-EXPORT-POLICY-V1"
EXPORT_PROJECTION_VERSION="AUDIT-EVENT-SAFE-V1"
EXPORT_FORMAT="JSONL_V1"
EXPORT_PURPOSES=frozenset({"SECURITY_REVIEW","COMPLIANCE_REVIEW","PROJECT_GOVERNANCE","INCIDENT_INVESTIGATION"})
_STAGES=frozenset({"CAPTURE","RENDER","PUBLISH"})


def _scope(scope,project_id):
    if (type(scope) is not str or scope not in {"DEPLOYMENT","PROJECT"}
            or scope=="DEPLOYMENT" and project_id is not None
            or scope=="PROJECT" and (type(project_id) is not UUID or project_id.int==0)):
        raise ValueError("invalid Audit export scope")


def _utc(value):return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")


@dataclass(frozen=True,slots=True)
class AuditExportSpec:
    scope: str
    project_id: UUID|None
    purpose: str
    start_at: datetime
    end_at: datetime
    action: str|None=None
    outcome: str|None=None
    actor_id: UUID|None=None  # Filter ONLY; not the authorized requesting actor.
    target_object_type: str|None=None
    target_object_id: UUID|None=None
    trace_id: UUID|None=None

    def __post_init__(self):
        _scope(self.scope,self.project_id)
        if (type(self.purpose) is not str or self.purpose not in EXPORT_PURPOSES
                or self.scope=="DEPLOYMENT" and self.purpose=="PROJECT_GOVERNANCE"):
            raise ValueError("invalid Audit export purpose")
        self.as_search()

    def as_search(self):
        """Batch size is server-owned; this query is not a capture snapshot."""
        return AuditSearch(self.start_at,self.end_at,page_size=200,action=self.action,outcome=self.outcome,
            actor_id=self.actor_id,target_object_type=self.target_object_type,
            target_object_id=self.target_object_id,trace_id=self.trace_id)

    def fingerprint(self):
        """Stable consistency hash, NOT authority, signature or source membership."""
        self.__post_init__()
        ref=lambda value:str(value) if value is not None else None
        payload=dict(scope=self.scope,project=ref(self.project_id),purpose=self.purpose,
            start=_utc(self.start_at),end=_utc(self.end_at),action=self.action,outcome=self.outcome,
            actor=ref(self.actor_id),object_type=self.target_object_type,object_id=ref(self.target_object_id),
            trace=ref(self.trace_id),format=EXPORT_FORMAT,projection=EXPORT_PROJECTION_VERSION,policy=EXPORT_POLICY_VERSION)
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()


@dataclass(frozen=True,slots=True)
class AuditExportAuthorityRequest:
    """Owner-bound lookup coordinates ONLY, not reusable access credentials."""
    export_id: UUID
    actor_id: UUID
    scope: str
    project_id: UUID|None
    stage: str

    def __post_init__(self):
        _scope(self.scope,self.project_id)
        if (any(type(value) is not UUID or value.int==0 for value in (self.export_id,self.actor_id))
                or type(self.stage) is not str or self.stage not in _STAGES):
            raise ValueError("invalid Audit export authority request")


class AuditExportCurrentAuthorityPort(Protocol):
    def assert_current(self,transaction:object,*,request:AuditExportAuthorityRequest)->None:
        """Trusted implementation MUST lock/recheck current facts or raise.

        Owner must bind coordinates to its stored export first. Auth must lock
        an actual enabled User and current deployment role, or Project must
        lock/recheck actual PM/member/department and archived read exception.
        Locks last until this caller transaction ends. Historical Actor UUID,
        purpose, DTO, lease token or a boolean is NEVER sufficient proof.
        No raw Session/CSRF/credentials in Job payload or persisted export.
        This declaration supplies no implementation or permissive fallback.
        """
        ...
