"""Deterministic, domain-separated upload token; no plaintext database storage."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from typing import Protocol


class UploadTokenKeyProvider(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class HmacUploadTokenIssuer:
    def __init__(self, *, provider: UploadTokenKeyProvider, key_ref: str) -> None:
        if provider is None or type(key_ref) is not str or not key_ref:
            raise ValueError("Upload token key source is required")
        self._provider, self._key_ref = provider, key_ref

    def issue(self, *, upload_id: uuid.UUID, actor_id: uuid.UUID,
              scope: str, project_id: uuid.UUID | None) -> tuple[str, bytes]:
        if (type(upload_id) is not uuid.UUID or upload_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (type(project_id) is not uuid.UUID or project_id.int == 0)):
            raise ValueError("Invalid upload token binding")
        key = self._provider.resolve_key(self._key_ref)
        if type(key) is not bytes or len(key) != 32:
            raise RuntimeError("Upload token key unavailable")
        message = (b"plm-upload-token-v1\0" + upload_id.bytes + actor_id.bytes
                   + (b"P" + project_id.bytes if scope == "PROJECT" else b"G"))
        raw = hmac.digest(key, message, "sha256")
        token = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        return token, hashlib.sha256(token.encode("ascii")).digest()
