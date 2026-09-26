"""Version-scoped, non-secret command replay descriptors."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.platform.application.errors import ApplicationError


_OPERATION = re.compile(r"V[1-9][0-9]*_[A-Z][A-Z0-9_]{2,120}\Z", re.ASCII)


class IdempotencyError(ApplicationError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_idempotency_key(key: str) -> str:
    if (type(key) is not str or not 16 <= len(key) <= 128
            or any(not 32 <= ord(char) <= 126 for char in key)):
        raise IdempotencyError("VALIDATION_FAILED")
    return key


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    actor_id: uuid.UUID
    project_id: uuid.UUID | None
    operation: str
    key_digest: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.actor_id) is not uuid.UUID or self.actor_id.int == 0
                or self.project_id is not None and (type(self.project_id) is not uuid.UUID or self.project_id.int == 0)
                or type(self.operation) is not str or len(self.operation) > 128
                or _OPERATION.fullmatch(self.operation) is None
                or type(self.key_digest) is not bytes or len(self.key_digest) != 32):
            raise IdempotencyError("VALIDATION_FAILED")

    @classmethod
    def from_key(cls, *, actor_id: uuid.UUID, project_id: uuid.UUID | None,
                 operation: str, key: str) -> IdempotencyScope:
        if (type(actor_id) is not uuid.UUID or actor_id.int == 0
                or project_id is not None and (type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(operation) is not str or len(operation) > 128
                or _OPERATION.fullmatch(operation) is None):
            raise IdempotencyError("VALIDATION_FAILED")
        return cls(actor_id, project_id, operation,
                   hashlib.sha256(validate_idempotency_key(key).encode("ascii")).digest())


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    ref_type: str
    ref_id: uuid.UUID
    status_code: int

    def __post_init__(self) -> None:
        if (type(self.ref_type) is not str or len(self.ref_type) > 128
                or _OPERATION.fullmatch(self.ref_type) is None
                or type(self.ref_id) is not uuid.UUID or self.ref_id.int == 0
                or type(self.status_code) is not int or not 200 <= self.status_code <= 299):
            raise IdempotencyError("VALIDATION_FAILED")


def canonical_payload_fingerprint(payload: object) -> bytes:
    """Hash a caller-normalized JSON payload without persisting its content."""

    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise IdempotencyError("VALIDATION_FAILED") from None
    if len(encoded) > 1_048_576:
        raise IdempotencyError("VALIDATION_FAILED")
    return hashlib.sha256(encoded).digest()
