"""Provider-neutral execution route, send proof and response memory contract."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_EGRESS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_PATH = re.compile(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\Z")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_FINISH = frozenset({"STOP", "LENGTH", "TOOL_CALL", "CONTENT_FILTER", "UNKNOWN"})


class AIProviderExecutionError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_EXECUTION_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


def safe_https_endpoint(value: object) -> bool:
    """Accept one exact public HTTPS origin/path; never credentials or redirects."""
    if type(value) is not str:
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or parts.port is not None
                or parts.query or parts.fragment or parts.netloc != host
                or host != host.lower() or host.endswith(".")
                or host in {"localhost", "localhost.localdomain"}
                or _PATH.fullmatch(parts.path) is None
                or len(host) > 253 or len(host.split(".")) < 2
                or any(_LABEL.fullmatch(label) is None
                       for label in host.split("."))):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class AIProviderExecutionRoute:
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    provider_kind: ProviderKind
    endpoint_policy_ref: str
    endpoint_url: str = field(repr=False)
    secret_ref: uuid.UUID = field(repr=False)
    secret_version_id: uuid.UUID = field(repr=False)
    provider_model_key: str
    model_revision: str
    data_region: str
    egress_class: str
    max_response_bytes: int
    connect_timeout_seconds: int
    read_timeout_seconds: int
    total_timeout_seconds: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.ai_provider_id, self.provider_config_version_id,
                    self.ai_model_id, self.secret_ref, self.secret_version_id))
                or self.provider_kind is not ProviderKind.OPENAI_COMPATIBLE
                or type(self.endpoint_policy_ref) is not str
                or _REF.fullmatch(self.endpoint_policy_ref) is None
                or not safe_https_endpoint(self.endpoint_url)
                or type(self.provider_model_key) is not str
                or _MODEL.fullmatch(self.provider_model_key) is None
                or type(self.model_revision) is not str
                or _MODEL.fullmatch(self.model_revision) is None
                or type(self.data_region) is not str
                or _REGION.fullmatch(self.data_region) is None
                or type(self.egress_class) is not str
                or _EGRESS.fullmatch(self.egress_class) is None
                or type(self.max_response_bytes) is not int
                or not 1 <= self.max_response_bytes <= 100_000_000
                or any(type(value) is not int or not 1 <= value <= 120
                       for value in (
                           self.connect_timeout_seconds,
                           self.read_timeout_seconds,
                           self.total_timeout_seconds,
                       ))
                or self.connect_timeout_seconds > self.total_timeout_seconds
                or self.read_timeout_seconds > self.total_timeout_seconds):
            raise AIProviderExecutionError("AI_PROVIDER_ROUTE_INVALID")


def provider_route_fingerprint(route: AIProviderExecutionRoute) -> bytes:
    if type(route) is not AIProviderExecutionRoute:
        raise AIProviderExecutionError("AI_PROVIDER_ROUTE_INVALID")
    route.__post_init__()
    return canonical_payload_fingerprint({
        "ai_provider_id": str(route.ai_provider_id),
        "provider_config_version_id": str(route.provider_config_version_id),
        "ai_model_id": str(route.ai_model_id),
        "provider_kind": route.provider_kind.value,
        "endpoint_policy_ref": route.endpoint_policy_ref,
        "endpoint_url": route.endpoint_url,
        "secret_ref": str(route.secret_ref),
        "secret_version_id": str(route.secret_version_id),
        "provider_model_key": route.provider_model_key,
        "model_revision": route.model_revision,
        "data_region": route.data_region,
        "egress_class": route.egress_class,
        "max_response_bytes": route.max_response_bytes,
        "connect_timeout_seconds": route.connect_timeout_seconds,
        "read_timeout_seconds": route.read_timeout_seconds,
        "total_timeout_seconds": route.total_timeout_seconds,
    })


@dataclass(frozen=True, slots=True)
class AIProviderSendProof:
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID
    job_id: uuid.UUID
    attempt_no: int
    fencing_token: int
    content_plan_id: uuid.UUID
    authorization_ref: uuid.UUID
    grant_fingerprint: bytes = field(repr=False)
    route_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    payload_bytes: int
    input_tokens: int
    valid_until: datetime

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.ai_task_id, self.ai_invocation_id, self.job_id,
                    self.content_plan_id, self.authorization_ref))
                or type(self.attempt_no) is not int
                or not 1 <= self.attempt_no <= 10
                or type(self.fencing_token) is not int
                or not 1 <= self.fencing_token <= 2_147_483_647
                or not all(_digest(value) for value in (
                    self.grant_fingerprint, self.route_fingerprint,
                    self.payload_fingerprint))
                or type(self.payload_bytes) is not int or self.payload_bytes < 1
                or type(self.input_tokens) is not int or self.input_tokens < 1
                or not isinstance(self.valid_until, datetime)
                or self.valid_until.tzinfo is None
                or self.valid_until.utcoffset() is None):
            raise AIProviderExecutionError("AI_PROVIDER_SEND_PROOF_INVALID")


def require_provider_send(
    proof: AIProviderSendProof,
    route: AIProviderExecutionRoute,
    envelope: AIExecutionEnvelope,
    *, now: datetime,
) -> AIProviderSendProof:
    if (type(proof) is not AIProviderSendProof
            or type(route) is not AIProviderExecutionRoute
            or type(envelope) is not AIExecutionEnvelope
            or not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise AIProviderExecutionError("AI_PROVIDER_SEND_NOT_AUTHORIZED")
    try:
        proof.__post_init__()
        route.__post_init__()
        envelope.__post_init__()
    except Exception:
        raise AIProviderExecutionError("AI_PROVIDER_SEND_NOT_AUTHORIZED") from None
    if (now.astimezone(timezone.utc)
            >= proof.valid_until.astimezone(timezone.utc)
            or proof.content_plan_id != envelope.content_plan_id
            or not hmac.compare_digest(
                proof.route_fingerprint, provider_route_fingerprint(route))
            or not hmac.compare_digest(
                proof.payload_fingerprint, envelope.payload_fingerprint)
            or proof.payload_bytes != envelope.payload_bytes
            or proof.input_tokens != envelope.input_tokens):
        raise AIProviderExecutionError("AI_PROVIDER_SEND_NOT_AUTHORIZED")
    return proof


@dataclass(frozen=True, slots=True)
class AIProviderResponseObservation:
    response_fingerprint: bytes = field(repr=False)
    response_bytes: int
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    finish_reason: str

    def __post_init__(self) -> None:
        optional_tokens = (self.input_tokens, self.output_tokens)
        if (not _digest(self.response_fingerprint)
                or type(self.response_bytes) is not int
                or not 1 <= self.response_bytes <= 100_000_000
                or any(value is not None and (
                    type(value) is not int or not 0 <= value <= 1_073_741_824)
                    for value in optional_tokens)
                or type(self.latency_ms) is not int
                or not 0 <= self.latency_ms <= 86_400_000
                or self.finish_reason not in _FINISH):
            raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_INVALID")


class AIProviderResponse:
    """Own raw response bytes until P07 consumes them; close zeroes memory."""

    __slots__ = ("observation", "_body", "_closed")

    def __init__(self, body: bytearray, observation: AIProviderResponseObservation) -> None:
        if (type(body) is not bytearray or not body
                or type(observation) is not AIProviderResponseObservation):
            raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_INVALID")
        observation.__post_init__()
        if (len(body) != observation.response_bytes
                or not hmac.compare_digest(
                    hashlib.sha256(body).digest(),
                    observation.response_fingerprint)):
            raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_INVALID")
        self.observation = observation
        self._body = body
        self._closed = False

    def __repr__(self) -> str:
        return ("AIProviderResponse(observation="
                + repr(self.observation) + ", closed=" + str(self._closed) + ")")

    def __enter__(self) -> AIProviderResponse:
        if self._closed:
            raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_CLOSED")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def view(self) -> memoryview:
        if self._closed:
            raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_CLOSED")
        return memoryview(self._body).toreadonly()

    def close(self) -> None:
        if not self._closed:
            self._body[:] = b"\x00" * len(self._body)
            self._closed = True


class AIProviderAdapterPort(Protocol):
    def send(
        self, *, route: AIProviderExecutionRoute, proof: AIProviderSendProof,
        envelope: AIExecutionEnvelope, key: memoryview,
    ) -> AIProviderResponse: ...
