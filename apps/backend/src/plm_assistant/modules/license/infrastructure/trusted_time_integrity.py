"""Keyed integrity for trusted-time state; key source is injected and never persisted."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.trusted_time import TrustedTimeError, TrustedTimeRecord


class TrustedTimeKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None:
        """Return a deployment secret from a separate protected store, never the database."""


class HmacTrustedTimeIntegrity:
    ALGORITHM = "HMAC-SHA256-V1"

    def __init__(self, resolver: TrustedTimeKeyResolverPort, *, key_ref: str) -> None:
        if resolver is None or type(key_ref) is not str or not 1 <= len(key_ref) <= 128:
            raise ValueError("trusted-time key resolver and reference are required")
        self._resolver = resolver
        self._key_ref = key_ref

    def sign(self, record: TrustedTimeRecord) -> dict[str, str]:
        if record.last_successful_time is None or record.state_version < 1 or record.last_event_ref is None:
            raise TrustedTimeError("TRUST_STATE_INVALID")
        tag = self._tag(record)
        return {"algorithm": self.ALGORITHM, "key_ref": self._key_ref, "tag": tag}

    def verify(self, record: TrustedTimeRecord) -> bool:
        if (record.last_successful_time is None and record.state_version == 0
                and record.integrity_metadata is None and record.last_event_ref is None):
            return True
        metadata = record.integrity_metadata
        if (type(metadata) is not dict or set(metadata) != {"algorithm", "key_ref", "tag"}
                or metadata.get("algorithm") != self.ALGORITHM
                or metadata.get("key_ref") != self._key_ref
                or type(metadata.get("tag")) is not str or len(metadata["tag"]) != 64):
            return False
        try:
            return hmac.compare_digest(self._tag(record), metadata["tag"])
        except (ValueError, TrustedTimeError):
            return False

    def _tag(self, record: TrustedTimeRecord) -> str:
        key = self._resolver.resolve_key(self._key_ref)
        if type(key) is not bytes or len(key) < 32:
            raise TrustedTimeError("TRUST_STATE_INVALID")
        message = _canonical(record)
        mutable_key = bytearray(key)
        try:
            return hmac.new(mutable_key, message, hashlib.sha256).hexdigest()
        finally:
            mutable_key[:] = b"\x00" * len(mutable_key)


def _canonical(record: TrustedTimeRecord) -> bytes:
    moment = record.last_successful_time
    if (type(record.state_id) is not uuid.UUID or record.state_id.int == 0
            or type(record.last_event_ref) is not uuid.UUID or record.last_event_ref.int == 0
            or type(record.state_version) is not int or record.state_version < 1
            or not isinstance(moment, datetime) or moment.tzinfo is None
            or moment.utcoffset() is None):
        raise TrustedTimeError("TRUST_STATE_INVALID")
    utc = moment.astimezone(timezone.utc)
    return (f"plm-trusted-time-v1\n{record.state_id}\n{record.state_version}\n"
            f"{utc.isoformat(timespec='microseconds')}\n{record.last_event_ref}\n").encode("ascii")
