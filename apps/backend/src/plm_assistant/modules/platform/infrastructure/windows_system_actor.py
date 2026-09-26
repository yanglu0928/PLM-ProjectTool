"""Read-only, account-bound Worker identity; no User, Session or privileges."""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol
from uuid import UUID

from plm_assistant.modules.platform.application.system_actor import SystemActorUnavailable

WORKER_SYSTEM_ACTOR_KEY_REF = "worker-system-actor-v1"
_DOMAIN = b"PLM-WORKER-SYSTEM-ACTOR-V1\x00"


class SystemActorMaterialPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class WindowsSystemActor:
    """Pins a deployment identity at construction and rereads it on every use.

    Only the dedicated Vault reference is used. Source material is never retained
    by this adapter, returned or used for signing. A changed or missing source
    is a configuration failure, not a reason to invent a replacement identity.
    """

    def __init__(self, *, resolver: SystemActorMaterialPort) -> None:
        self._resolver = resolver
        self._fingerprint = self._read()

    def _read(self) -> bytes:
        try:
            material = self._resolver.resolve_key(WORKER_SYSTEM_ACTOR_KEY_REF)
            if type(material) is not bytes or len(material) != 32:
                raise SystemActorUnavailable()
            fingerprint = hashlib.sha256(_DOMAIN + material).digest()
            if UUID(bytes=fingerprint[:16]).int == 0:
                raise SystemActorUnavailable()
            return fingerprint
        except Exception:
            raise SystemActorUnavailable() from None

    def assert_current(self) -> UUID:
        if not hmac.compare_digest(self._read(), self._fingerprint):
            raise SystemActorUnavailable()
        return UUID(bytes=self._fingerprint[:16])
