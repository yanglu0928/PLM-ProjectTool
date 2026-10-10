from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .errors import LicenseError
from .mac import MacCandidate, machine_fingerprint, select_mac
from .time_guard import SystemTimeGuard, require_utc


FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LICENSE_SCHEMA = "plm.license.v1"
REQUEST_SCHEMA = "plm.license-request.v1"


def _format_time(value: datetime) -> str:
    return require_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise LicenseError("LICENSE_PAYLOAD_INVALID", f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LicenseError("LICENSE_PAYLOAD_INVALID", f"{field} must be an ISO-8601 timestamp") from exc
    return require_utc(parsed)


@dataclass(frozen=True)
class LicensePayload:
    license_id: str
    customer: str
    machine_fingerprint: str
    valid_from: str
    valid_to: str
    issue_time: str
    schema_version: str = LICENSE_SCHEMA

    @classmethod
    def create(
        cls,
        *,
        license_id: str,
        customer: str,
        machine_fingerprint: str,
        valid_from: datetime,
        valid_to: datetime,
        issue_time: datetime,
    ) -> "LicensePayload":
        return cls(
            license_id=license_id,
            customer=customer,
            machine_fingerprint=machine_fingerprint,
            valid_from=_format_time(valid_from),
            valid_to=_format_time(valid_to),
            issue_time=_format_time(issue_time),
        ).validated()

    @classmethod
    def from_dict(cls, raw: Any) -> "LicensePayload":
        required = {"license_id", "customer", "machine_fingerprint", "valid_from", "valid_to", "issue_time", "schema_version"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "License payload fields are incomplete or unexpected")
        try:
            payload = cls(**raw)
        except TypeError as exc:
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "License payload cannot be constructed") from exc
        return payload.validated()

    def validated(self) -> "LicensePayload":
        if self.schema_version != LICENSE_SCHEMA:
            raise LicenseError("LICENSE_SCHEMA_UNSUPPORTED", "License schema version is not supported")
        if not isinstance(self.license_id, str) or not self.license_id.strip():
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "license_id is required")
        if not isinstance(self.customer, str) or not self.customer.strip():
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "customer is required")
        if not isinstance(self.machine_fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(self.machine_fingerprint):
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "machine_fingerprint must be a SHA-256 hex digest")
        valid_from = _parse_time(self.valid_from, "valid_from")
        valid_to = _parse_time(self.valid_to, "valid_to")
        issue_time = _parse_time(self.issue_time, "issue_time")
        if valid_from > valid_to or issue_time > valid_to:
            raise LicenseError("LICENSE_PAYLOAD_INVALID", "License time range is invalid")
        return self

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class LicenseDocument:
    algorithm: str
    payload: dict[str, Any]
    signature: str

    def as_dict(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm, "payload": self.payload, "signature": self.signature}

    @classmethod
    def from_dict(cls, raw: Any) -> "LicenseDocument":
        if not isinstance(raw, dict) or set(raw) != {"algorithm", "payload", "signature"}:
            raise LicenseError("LICENSE_DOCUMENT_INVALID", "License document fields are incomplete or unexpected")
        if raw["algorithm"] != "Ed25519" or not isinstance(raw["signature"], str):
            raise LicenseError("LICENSE_DOCUMENT_INVALID", "License document algorithm or signature is invalid")
        return cls(raw["algorithm"], raw["payload"], raw["signature"])


def create_license_request(candidates: list[MacCandidate], selected_mac: str | None) -> dict[str, str]:
    selected = select_mac(candidates, selected_mac)
    return {"schema_version": REQUEST_SCHEMA, "machine_fingerprint": machine_fingerprint(selected.mac)}


def public_key_to_base64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def _load_public_key(public_key_base64: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(public_key_base64, validate=True)
        if len(raw) != 32:
            raise ValueError("wrong key size")
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise LicenseError("LICENSE_PUBLIC_KEY_INVALID", "Ed25519 public key is invalid") from exc


def issue_license(payload: LicensePayload, private_key: Ed25519PrivateKey) -> LicenseDocument:
    payload = payload.validated()
    signature = private_key.sign(payload.canonical_bytes())
    return LicenseDocument("Ed25519", asdict(payload), base64.b64encode(signature).decode("ascii"))


def verify_license(
    document_raw: dict[str, Any],
    *,
    public_key_base64: str,
    current_mac: str,
    now: datetime | None = None,
    time_guard: SystemTimeGuard | None = None,
) -> LicensePayload:
    document = LicenseDocument.from_dict(document_raw)
    payload = LicensePayload.from_dict(document.payload)
    public_key = _load_public_key(public_key_base64)
    try:
        signature = base64.b64decode(document.signature, validate=True)
        public_key.verify(signature, payload.canonical_bytes())
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise LicenseError("LICENSE_SIGNATURE_INVALID", "License signature verification failed") from exc

    expected = machine_fingerprint(current_mac)
    if not hmac.compare_digest(expected, payload.machine_fingerprint):
        raise LicenseError("LICENSE_MACHINE_MISMATCH", "License does not match the selected machine MAC")

    current = require_utc(now or datetime.now(timezone.utc))
    if time_guard is not None:
        current = time_guard.validate(current)
    issue_time = _parse_time(payload.issue_time, "issue_time")
    valid_from = _parse_time(payload.valid_from, "valid_from")
    valid_to = _parse_time(payload.valid_to, "valid_to")
    if current < issue_time:
        raise LicenseError("LICENSE_SYSTEM_TIME_INVALID", "System time is earlier than the license issue time")
    if current < valid_from:
        raise LicenseError("LICENSE_NOT_YET_VALID", "License validity period has not started")
    if current > valid_to:
        raise LicenseError("LICENSE_EXPIRED", "License has expired")
    if time_guard is not None:
        time_guard.commit(current)
    return payload
