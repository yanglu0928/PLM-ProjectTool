"""Versioned AI Task policy and locked Prompt submission snapshot owner."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol


_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_PARAMETER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_TYPES = frozenset({"STRING", "INTEGER", "BOOLEAN"})


class AITaskSubmissionPolicyError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_POLICY_INVALID") -> None:
        self.code = code
        super().__init__(code)


class AITaskPromptOwnerError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_PROMPT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AITaskParameterField:
    name: str
    value_type: str
    required: bool = False
    max_length: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (type(self.name) is not str or _PARAMETER.fullmatch(self.name) is None
                or self.value_type not in _TYPES or type(self.required) is not bool
                or (self.max_length is not None
                    and (type(self.max_length) is not int or not 1 <= self.max_length <= 4096))
                or (self.minimum is not None and type(self.minimum) is not int)
                or (self.maximum is not None and type(self.maximum) is not int)
                or (self.minimum is not None and self.maximum is not None
                    and self.minimum > self.maximum)
                or type(self.allowed_values) is not tuple
                or len(set(self.allowed_values)) != len(self.allowed_values)
                or any(type(item) is not str or not item or len(item) > 4096
                       for item in self.allowed_values)
                or (self.value_type != "STRING"
                    and (self.max_length is not None or self.allowed_values))
                or (self.value_type != "INTEGER"
                    and (self.minimum is not None or self.maximum is not None))):
            raise ValueError("invalid AI Task parameter field")

    def accepts(self, value: object) -> bool:
        if self.value_type == "STRING":
            return bool(type(value) is str and value == value.strip() and value
                        and len(value) <= (self.max_length or 4096)
                        and (not self.allowed_values or value in self.allowed_values))
        if self.value_type == "INTEGER":
            return bool(type(value) is int
                        and (self.minimum is None or value >= self.minimum)
                        and (self.maximum is None or value <= self.maximum))
        return type(value) is bool


@dataclass(frozen=True, slots=True)
class AITaskSubmissionPolicy:
    reference: str
    policy_version: int
    task_type: str
    prompt_template_id: uuid.UUID
    purpose_ref: str
    output_schema_ref: str
    context_policy_ref: str
    parameter_fields: tuple[AITaskParameterField, ...] = ()

    def __post_init__(self) -> None:
        refs = (self.reference, self.purpose_ref, self.output_schema_ref,
                self.context_policy_ref)
        names = tuple(item.name for item in self.parameter_fields)
        if (any(type(value) is not str or _REF.fullmatch(value) is None for value in refs)
                or type(self.policy_version) is not int or not 1 <= self.policy_version <= 2_147_483_647
                or type(self.task_type) is not str or not self.task_type
                or type(self.prompt_template_id) is not uuid.UUID
                or not self.prompt_template_id.int
                or type(self.parameter_fields) is not tuple or len(self.parameter_fields) > 16
                or any(type(item) is not AITaskParameterField for item in self.parameter_fields)
                or len(set(names)) != len(names)):
            raise ValueError("invalid AI Task submission policy")


@dataclass(frozen=True, slots=True)
class ResolvedAITaskSubmissionPolicy:
    reference: str
    policy_version: int
    task_type: str
    prompt_template_id: uuid.UUID
    purpose_ref: str
    output_schema_ref: str
    context_policy_ref: str
    task_parameters_json: str = field(repr=False)


class AITaskSubmissionPolicyRegistry:
    """Immutable, explicit deployment policy; unknown or malformed input fails closed."""

    def __init__(self, policies: Mapping[str, AITaskSubmissionPolicy]) -> None:
        if (not isinstance(policies, Mapping) or not policies or len(policies) > 64
                or any(type(key) is not str or type(value) is not AITaskSubmissionPolicy
                       or key != value.reference for key, value in policies.items())):
            raise ValueError("AI Task submission policies required")
        self._policies = MappingProxyType(dict(policies))

    def snapshot(self) -> tuple[AITaskSubmissionPolicy, ...]:
        """Return the immutable, non-secret deployment policies in stable order."""
        return tuple(self._policies[key] for key in sorted(self._policies))

    def resolve(self, *, reference: str, task_type: str, output_schema_ref: str,
                context_policy_ref: str, parameters: dict[str, object]) -> ResolvedAITaskSubmissionPolicy:
        policy = self._policies.get(reference)
        if (type(policy) is not AITaskSubmissionPolicy or policy.task_type != task_type
                or policy.output_schema_ref != output_schema_ref
                or policy.context_policy_ref != context_policy_ref
                or type(parameters) is not dict or len(parameters) > 16
                or any(type(key) is not str or _PARAMETER.fullmatch(key) is None
                       for key in parameters)):
            raise AITaskSubmissionPolicyError()
        fields = {item.name: item for item in policy.parameter_fields}
        if set(parameters) - set(fields):
            raise AITaskSubmissionPolicyError()
        for name, rule in fields.items():
            if (rule.required and name not in parameters
                    or name in parameters and not rule.accepts(parameters[name])):
                raise AITaskSubmissionPolicyError()
        try:
            encoded = json.dumps(parameters, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError):
            raise AITaskSubmissionPolicyError() from None
        if len(encoded.encode("utf-8")) > 16_384:
            raise AITaskSubmissionPolicyError()
        return ResolvedAITaskSubmissionPolicy(
            policy.reference, policy.policy_version, policy.task_type,
            policy.prompt_template_id, policy.purpose_ref, policy.output_schema_ref,
            policy.context_policy_ref, encoded,
        )


@dataclass(frozen=True, slots=True)
class AITaskPromptSnapshot:
    prompt_template_ref: uuid.UUID
    prompt_version_no: int
    policy_ref: str
    policy_version: int
    purpose_ref: str
    output_schema_ref: str
    context_policy_ref: str
    task_parameters_json: str = field(repr=False)
    task_parameters_fingerprint: bytes = field(repr=False)


class AITaskPromptCurrentRepositoryPort(Protocol):
    def resolve_current(self, transaction: object, *,
                        policy: ResolvedAITaskSubmissionPolicy) -> AITaskPromptSnapshot | None: ...


class AITaskPromptOwner:
    def __init__(self, repository: AITaskPromptCurrentRepositoryPort) -> None:
        if repository is None:
            raise ValueError("AI Task Prompt repository required")
        self._repository = repository

    def resolve_current(self, transaction: object, *,
                        policy: ResolvedAITaskSubmissionPolicy) -> AITaskPromptSnapshot:
        if type(policy) is not ResolvedAITaskSubmissionPolicy:
            raise AITaskPromptOwnerError()
        snapshot = self._repository.resolve_current(transaction, policy=policy)
        if (type(snapshot) is not AITaskPromptSnapshot
                or snapshot.prompt_template_ref != policy.prompt_template_id
                or type(snapshot.prompt_version_no) is not int or snapshot.prompt_version_no < 1
                or snapshot.policy_ref != policy.reference
                or snapshot.policy_version != policy.policy_version
                or snapshot.purpose_ref != policy.purpose_ref
                or snapshot.output_schema_ref != policy.output_schema_ref
                or snapshot.context_policy_ref != policy.context_policy_ref
                or type(snapshot.task_parameters_json) is not str
                or not snapshot.task_parameters_json
                or type(snapshot.task_parameters_fingerprint) is not bytes
                or len(snapshot.task_parameters_fingerprint) != 32):
            raise AITaskPromptOwnerError()
        return snapshot
