"""Safe, immutable input for one append-only AuditEvent."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field


_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_OWNER = re.compile(r"[a-z][a-z0-9_]{0,39}\Z", re.ASCII)
_ROOT = re.compile(r"[A-Z]{2,3}-[0-9]{2}\Z", re.ASCII)


class AuditEventValidationError(ValueError):
    """Fixed-message rejection; never echo caller-provided values."""


def _uuid(value: object, *, optional: bool = False) -> bool:
    return value is None and optional or type(value) is uuid.UUID and value.int != 0


@dataclass(frozen=True, slots=True)
class AuditEventDraft:
    trace_id: uuid.UUID
    event_scope: str
    target_project_id: uuid.UUID | None
    actor_type: str
    actor_id: uuid.UUID | None
    original_actor_id: uuid.UUID | None
    actor_hint_digest: bytes | None = field(repr=False)
    action: str
    outcome: str
    target_owner_module: str | None = None
    target_object_type: str | None = None
    target_object_id: uuid.UUID | None = None
    target_version_id: uuid.UUID | None = None
    reason_code: str | None = None
    before_state: str | None = None
    after_state: str | None = None

    def __post_init__(self) -> None:
        if not _uuid(self.trace_id):
            raise AuditEventValidationError("audit trace_id is invalid")
        if self.event_scope == "DEPLOYMENT":
            if self.target_project_id is not None:
                raise AuditEventValidationError("audit scope is invalid")
        elif self.event_scope == "PROJECT":
            if not _uuid(self.target_project_id):
                raise AuditEventValidationError("audit scope is invalid")
        else:
            raise AuditEventValidationError("audit scope is invalid")
        if not _uuid(self.actor_id, optional=True) or not _uuid(self.original_actor_id, optional=True):
            raise AuditEventValidationError("audit actor is invalid")
        digest = self.actor_hint_digest
        if digest is not None and (type(digest) is not bytes or len(digest) != 32):
            raise AuditEventValidationError("audit actor is invalid")
        if self.actor_type == "USER":
            valid_actor = self.actor_id is not None and self.original_actor_id is None and digest is None
        elif self.actor_type == "SYSTEM":
            valid_actor = self.actor_id is not None and self.original_actor_id is not None and digest is None
        elif self.actor_type == "UNRESOLVED":
            valid_actor = self.actor_id is None and self.original_actor_id is None
        else:
            valid_actor = False
        if not valid_actor:
            raise AuditEventValidationError("audit actor is invalid")
        if self.outcome not in ("SUCCESS", "DENIED", "FAILED"):
            raise AuditEventValidationError("audit outcome is invalid")
        if type(self.action) is not str or not _CODE.fullmatch(self.action):
            raise AuditEventValidationError("audit action is invalid")
        for value in (self.reason_code, self.before_state, self.after_state):
            if value is not None and (type(value) is not str or not _CODE.fullmatch(value)):
                raise AuditEventValidationError("audit summary is invalid")
        target = (self.target_owner_module, self.target_object_type, self.target_object_id)
        if all(part is None for part in target):
            if self.target_version_id is not None:
                raise AuditEventValidationError("audit target is invalid")
        elif not (
            type(self.target_owner_module) is str
            and _OWNER.fullmatch(self.target_owner_module)
            and type(self.target_object_type) is str
            and _ROOT.fullmatch(self.target_object_type)
            and _uuid(self.target_object_id)
        ):
            raise AuditEventValidationError("audit target is invalid")
        if not _uuid(self.target_version_id, optional=True):
            raise AuditEventValidationError("audit target is invalid")
