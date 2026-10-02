"""Offline Provider probe planning; no network, Secret read or egress grant."""

from __future__ import annotations

import ipaddress
import re
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint


_REFERENCE = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_EGRESS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_PATH = re.compile(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\Z")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
PROBE_ID = "CHAT_CONNECTIVITY_V1"
PROBE_TEXT = "ping"


class ProbePolicyError(ValueError):
    def __init__(self) -> None:
        super().__init__("provider probe policy unavailable")


def _safe_endpoint_url(value: str) -> bool:
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
                or any(_LABEL.fullmatch(label) is None for label in host.split("."))):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class EndpointProbePolicy:
    """Trusted deployment policy, never built from a Provider API request."""

    reference: str
    kind: ProviderKind
    endpoint_url: str
    model_key: str
    data_region: str
    egress_class: str

    def __post_init__(self) -> None:
        if (type(self.reference) is not str or _REFERENCE.fullmatch(self.reference) is None
                or type(self.kind) is not ProviderKind
                or self.kind is not ProviderKind.OPENAI_COMPATIBLE
                or not _safe_endpoint_url(self.endpoint_url)
                or type(self.model_key) is not str or _MODEL.fullmatch(self.model_key) is None
                or type(self.data_region) is not str or _REGION.fullmatch(self.data_region) is None
                or type(self.egress_class) is not str or _EGRESS.fullmatch(self.egress_class) is None):
            raise ProbePolicyError()


@dataclass(frozen=True, slots=True)
class ProviderProbePlan:
    provider_id: uuid.UUID
    config_version: int
    policy_ref: str
    endpoint_url: str
    model_key: str
    secret_ref: uuid.UUID
    probe_id: str = PROBE_ID

    def __post_init__(self) -> None:
        if (type(self.provider_id) is not uuid.UUID or not self.provider_id.int
                or type(self.config_version) is not int or self.config_version < 1
                or type(self.policy_ref) is not str or _REFERENCE.fullmatch(self.policy_ref) is None
                or not _safe_endpoint_url(self.endpoint_url)
                or type(self.model_key) is not str or _MODEL.fullmatch(self.model_key) is None
                or type(self.secret_ref) is not uuid.UUID or not self.secret_ref.int
                or self.probe_id != PROBE_ID):
            raise ProbePolicyError()

    @property
    def fixed_text(self) -> str:
        return PROBE_TEXT


class EndpointProbeRegistry:
    """Exact policy lookup; destination and model never come from Provider input."""

    def __init__(self, policies: Mapping[str, EndpointProbePolicy]) -> None:
        if (not isinstance(policies, Mapping) or not policies
                or any(type(key) is not str or type(value) is not EndpointProbePolicy
                       or key != value.reference for key, value in policies.items())):
            raise ProbePolicyError()
        self._policies = MappingProxyType(dict(policies))

    def plan(self, config: ProviderConfiguration) -> ProviderProbePlan:
        if type(config) is not ProviderConfiguration:
            raise ProbePolicyError()
        policy = self._policies.get(config.endpoint_policy_ref)
        if (policy is None or policy.kind is not config.kind
                or policy.data_region != config.data_region
                or policy.egress_class != config.egress_class
                or ProviderCapability.CHAT not in config.capabilities):
            raise ProbePolicyError()
        return ProviderProbePlan(
            provider_id=config.provider_id,
            config_version=config.config_version,
            policy_ref=policy.reference,
            endpoint_url=policy.endpoint_url,
            model_key=policy.model_key,
            secret_ref=config.secret_ref,
        )


def probe_policy_sha256(config: ProviderConfiguration, plan: ProviderProbePlan) -> bytes:
    """Canonical trusted policy fingerprint shared by submit and preflight."""
    if (type(config) is not ProviderConfiguration or type(plan) is not ProviderProbePlan
            or plan.provider_id != config.provider_id
            or plan.config_version != config.config_version
            or plan.policy_ref != config.endpoint_policy_ref
            or plan.secret_ref != config.secret_ref):
        raise ProbePolicyError()
    plan.__post_init__()
    return canonical_payload_fingerprint({
        "probe_id": plan.probe_id, "policy_ref": plan.policy_ref,
        "endpoint_url": plan.endpoint_url, "model_key": plan.model_key,
        "provider_kind": config.kind.value,
        "data_region": config.data_region,
        "egress_class": config.egress_class,
    })
