"""Immutable AI-01 provider configuration shape, not activation or egress proof."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import StrEnum


_POLICY_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_EGRESS_CLASS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class ProviderConfigurationError(ValueError):
    """Safe shape error that never reflects submitted configuration values."""

    def __init__(self) -> None:
        super().__init__("invalid AI provider configuration")


class ProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    ANTHROPIC_MESSAGES = "ANTHROPIC_MESSAGES"
    GEMINI_NATIVE = "GEMINI_NATIVE"
    CUSTOM = "CUSTOM"


class ProviderCapability(StrEnum):
    CHAT = "CHAT"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    EMBEDDING = "EMBEDDING"
    RERANK = "RERANK"


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    """One versioned deployment configuration; no Key, endpoint URL or payload.

    secret_ref is the opaque ID of a Platform SecretRef; the Application layer
    must resolve purpose and consumer before use. A well-formed configuration
    is not a connected or ACTIVE provider and never grants permission to
    transmit customer data. Those checks belong to the
    future AIService/ProviderAdapter and per-operation egress authorization.
    """

    provider_id: uuid.UUID
    config_version: int
    kind: ProviderKind
    display_name: str
    endpoint_policy_ref: str
    secret_ref: uuid.UUID
    data_region: str
    egress_class: str
    capabilities: frozenset[ProviderCapability]

    def __post_init__(self) -> None:
        if (
            type(self.provider_id) is not uuid.UUID
            or self.provider_id.int == 0
            or type(self.config_version) is not int
            or self.config_version < 1
            or type(self.kind) is not ProviderKind
            or type(self.display_name) is not str
            or not 1 <= len(self.display_name) <= 120
            or self.display_name != self.display_name.strip()
            or not self.display_name.isprintable()
            or type(self.endpoint_policy_ref) is not str
            or _POLICY_REF.fullmatch(self.endpoint_policy_ref) is None
            or type(self.secret_ref) is not uuid.UUID
            or self.secret_ref.int == 0
            or type(self.data_region) is not str
            or _REGION.fullmatch(self.data_region) is None
            or type(self.egress_class) is not str
            or _EGRESS_CLASS.fullmatch(self.egress_class) is None
            or type(self.capabilities) is not frozenset
            or not self.capabilities
            or any(type(item) is not ProviderCapability for item in self.capabilities)
        ):
            raise ProviderConfigurationError()
