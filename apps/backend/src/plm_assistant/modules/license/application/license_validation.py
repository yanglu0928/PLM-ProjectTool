"""Internal v1 full-bundle License validation under approved CR-LIC-001."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.license.application.signature_verifier import (
    LicenseSignatureError, LicenseSignatureVerifier,
)
from plm_assistant.modules.license.application.trusted_time import TrustedTimeError


SCHEMA_VERSION = "plm.license.v1"
PRODUCT_CODE = "PLM_PROJECT_TOOL"
_FIELDS = frozenset({"license_id", "customer", "machine_fingerprint", "valid_from",
                     "valid_to", "issue_time", "schema_version"})
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MAC = re.compile(r"[0-9A-F]{12}\Z", re.ASCII)


class LicenseValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SelectedMachinePort(Protocol):
    def selected_mac(self) -> str:
        """Return the operator-selected local MAC from trusted deployment configuration."""


class ProductPublicKeyPort(Protocol):
    def product_key_ref(self) -> str:
        """Return the trusted release key ref dedicated to this one product."""


class ClockPort(Protocol):
    def now_utc(self) -> datetime: ...


class TrustedTimeAdvancePort(Protocol):
    def advance(self, *, candidate: datetime, expected_version: int,
                trace_id: uuid.UUID, rollback_tolerance: timedelta) -> object: ...


@dataclass(frozen=True, slots=True)
class VerifiedFullBundleLicense:
    """Complete internal verification result, not an activated installation."""

    license_id: str
    customer: str = field(repr=False)
    document_sha256: bytes = field(repr=False)
    machine_fingerprint_hash: bytes = field(repr=False)
    valid_from: datetime
    valid_to: datetime
    validated_at: datetime
    product_code: str = PRODUCT_CODE
    grant_scope: str = "FULL_BUNDLE"


def normalize_mac(value: str) -> str:
    if type(value) is not str:
        raise LicenseValidationError("TRUST_STATE_INVALID")
    compact = re.sub(r"[:.\-\s]", "", value).upper()
    if not _MAC.fullmatch(compact) or compact in {"000000000000", "FFFFFFFFFFFF"}:
        raise LicenseValidationError("TRUST_STATE_INVALID")
    return ":".join(compact[index:index + 2] for index in range(0, 12, 2))


def machine_fingerprint_hash(value: str) -> bytes:
    return hashlib.sha256(normalize_mac(value).encode("ascii")).digest()


def _time(value: object) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise LicenseValidationError("MALFORMED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise LicenseValidationError("MALFORMED") from None


class LicenseService:
    def __init__(self, signature: LicenseSignatureVerifier,
                 machine: SelectedMachinePort, product_key: ProductPublicKeyPort,
                 clock: ClockPort, trusted_time: TrustedTimeAdvancePort,
                 *, rollback_tolerance: timedelta = timedelta(0)) -> None:
        if any(item is None for item in (signature, machine, product_key, clock, trusted_time)):
            raise ValueError("license verification dependencies are required")
        if (not isinstance(rollback_tolerance, timedelta)
                or not timedelta(0) <= rollback_tolerance <= timedelta(minutes=5)):
            raise ValueError("rollback tolerance is invalid")
        self._signature = signature
        self._machine = machine
        self._product_key = product_key
        self._clock = clock
        self._trusted_time = trusted_time
        self._rollback_tolerance = rollback_tolerance

    def validate(self, signed_document: bytes, *, expected_time_version: int,
                 trace_id: uuid.UUID, expected_public_key_ref: str | None = None) -> VerifiedFullBundleLicense:
        if type(expected_time_version) is not int or expected_time_version < 0 or type(trace_id) is not uuid.UUID or trace_id.int == 0:
            raise LicenseValidationError("TRUST_STATE_INVALID")
        try:
            key_ref = self._product_key.product_key_ref()
        except Exception:
            raise LicenseValidationError("TRUST_STATE_INVALID") from None
        if type(key_ref) is not str or not 1 <= len(key_ref) <= 128:
            raise LicenseValidationError("TRUST_STATE_INVALID")
        if expected_public_key_ref is not None and key_ref != expected_public_key_ref:
            raise LicenseValidationError("TRUST_STATE_INVALID")
        try:
            verified = self._signature.verify(signed_document, public_key_ref=key_ref)
        except LicenseSignatureError as exc:
            mapped = {"LICENSE_SIGNATURE_INVALID": "SIGNATURE_INVALID",
                      "LICENSE_PUBLIC_KEY_INVALID": "TRUST_STATE_INVALID"}.get(exc.code, "MALFORMED")
            raise LicenseValidationError(mapped) from None
        except Exception:
            raise LicenseValidationError("TRUST_STATE_INVALID") from None
        try:
            payload = json.loads(verified.canonical_payload)
        except (UnicodeError, json.JSONDecodeError):
            raise LicenseValidationError("MALFORMED") from None
        if type(payload) is not dict or set(payload) != _FIELDS:
            raise LicenseValidationError("MALFORMED")
        if payload["schema_version"] != SCHEMA_VERSION:
            raise LicenseValidationError("MALFORMED")
        license_id, customer, claimed_fingerprint = (payload[key] for key in ("license_id", "customer", "machine_fingerprint"))
        if (type(license_id) is not str or not 1 <= len(license_id) <= 128 or not license_id.strip()
                or type(customer) is not str or not 1 <= len(customer) <= 256 or not customer.strip()
                or type(claimed_fingerprint) is not str or not _FINGERPRINT.fullmatch(claimed_fingerprint)):
            raise LicenseValidationError("MALFORMED")
        valid_from, valid_to, issue_time = (_time(payload[key]) for key in ("valid_from", "valid_to", "issue_time"))
        if valid_from > valid_to or issue_time > valid_to:
            raise LicenseValidationError("MALFORMED")
        try:
            selected = self._machine.selected_mac()
            actual_fingerprint = machine_fingerprint_hash(selected)
        except Exception:
            raise LicenseValidationError("TRUST_STATE_INVALID") from None
        if not hmac.compare_digest(actual_fingerprint.hex(), claimed_fingerprint):
            raise LicenseValidationError("MACHINE_MISMATCH")
        try:
            now = self._clock.now_utc()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("timezone required")
            now = now.astimezone(timezone.utc)
        except Exception:
            raise LicenseValidationError("TRUST_STATE_INVALID") from None
        if now < issue_time or now < valid_from:
            raise LicenseValidationError("NOT_YET_VALID")
        if now > valid_to:
            raise LicenseValidationError("EXPIRED")
        try:
            self._trusted_time.advance(candidate=now, expected_version=expected_time_version,
                                       trace_id=trace_id, rollback_tolerance=self._rollback_tolerance)
        except TrustedTimeError as exc:
            raise LicenseValidationError("TIME_ROLLBACK" if exc.code == "TIME_ROLLBACK" else "TRUST_STATE_INVALID") from None
        except Exception:
            raise LicenseValidationError("TRUST_STATE_INVALID") from None
        return VerifiedFullBundleLicense(license_id, customer, verified.document_sha256,
                                         actual_fingerprint, valid_from, valid_to, now)
