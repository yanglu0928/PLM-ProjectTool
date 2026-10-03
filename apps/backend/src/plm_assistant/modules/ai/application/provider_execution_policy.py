"""Trusted deployment policy behind one opaque Provider endpoint reference."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType

from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind

from .provider_execution_contract import AIProviderExecutionError, safe_https_endpoint


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_EGRESS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


@dataclass(frozen=True, slots=True)
class AIProviderExecutionPolicy:
    reference: str
    provider_kind: ProviderKind
    endpoint_url: str
    data_region: str
    egress_class: str
    allowed_model_keys: frozenset[str]
    max_response_bytes: int
    connect_timeout_seconds: int
    read_timeout_seconds: int
    total_timeout_seconds: int

    def __post_init__(self) -> None:
        if (type(self.reference) is not str or _REF.fullmatch(self.reference) is None
                or self.provider_kind is not ProviderKind.OPENAI_COMPATIBLE
                or not safe_https_endpoint(self.endpoint_url)
                or type(self.data_region) is not str
                or _REGION.fullmatch(self.data_region) is None
                or type(self.egress_class) is not str
                or _EGRESS.fullmatch(self.egress_class) is None
                or type(self.allowed_model_keys) is not frozenset
                or not self.allowed_model_keys
                or any(type(value) is not str or _MODEL.fullmatch(value) is None
                       for value in self.allowed_model_keys)
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
            raise AIProviderExecutionError("AI_PROVIDER_POLICY_INVALID")


class AIProviderExecutionPolicyRegistry:
    """Resolve only policies supplied by the trusted deployment composition."""

    def __init__(self, policies: Iterable[AIProviderExecutionPolicy]) -> None:
        values = tuple(policies)
        if (not values
                or any(type(value) is not AIProviderExecutionPolicy for value in values)
                or len({value.reference for value in values}) != len(values)):
            raise ValueError("AI Provider execution policies required")
        for value in values:
            value.__post_init__()
        self._policies = MappingProxyType({value.reference: value for value in values})

    def resolve(
        self, *, reference: str, provider_kind: ProviderKind,
        data_region: str, egress_class: str, provider_model_key: str,
    ) -> AIProviderExecutionPolicy:
        policy = self._policies.get(reference)
        if (policy is None or policy.provider_kind is not provider_kind
                or policy.data_region != data_region
                or policy.egress_class != egress_class
                or provider_model_key not in policy.allowed_model_keys):
            raise AIProviderExecutionError("AI_PROVIDER_POLICY_NOT_AUTHORIZED")
        return policy
