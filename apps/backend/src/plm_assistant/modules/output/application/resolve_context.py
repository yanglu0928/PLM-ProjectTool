"""Fail-closed resolver for fixed Output inputs; performs no I/O itself."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest,
    OutputRequestError,
    ResolvedOutputContext,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)

_MAX_CONTEXT_BYTES = 1_048_576
_MAX_SOURCES = 64
_ALLOWED_JSON_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True, slots=True)
class FixedSourceVersion:
    """Authorized, immutable source projection returned by its owning module."""

    project_id: uuid.UUID
    source_version_ref: uuid.UUID
    source_kind: str
    review_state: str
    authorized: bool
    fields: Mapping[str, object] = field(repr=False)


@dataclass(frozen=True, slots=True)
class OutputTemplateVersion:
    template_version_ref: uuid.UUID
    output_type: str
    source_kinds: tuple[str, ...]
    immutable: bool = True
    published: bool = True


@dataclass(frozen=True, slots=True)
class OutputPolicyVersion:
    policy_ref: str
    allowed_template_versions: tuple[uuid.UUID, ...]
    allowed_output_types: tuple[str, ...]
    allowed_plugin_operations: tuple[str, ...]
    allowed_review_states: tuple[str, ...]
    fields_by_source_kind: Mapping[str, tuple[str, ...]]
    max_sources: int = 16
    max_context_bytes: int = 262_144


@dataclass(frozen=True, slots=True)
class PluginOperationCapability:
    operation_id: str
    output_types: tuple[str, ...]
    enabled: bool = False
    trusted: bool = False


class FixedOutputSourcePort(Protocol):
    def read_authorized_fixed_version(
        self, transaction: object, *, actor_id: uuid.UUID,
        project_id: uuid.UUID, source_version_ref: uuid.UUID,
    ) -> FixedSourceVersion | None: ...


class OutputTemplateRegistryPort(Protocol):
    def get_immutable_version(
        self, transaction: object, *, template_version_ref: uuid.UUID,
    ) -> OutputTemplateVersion | None: ...


class OutputPolicyRegistryPort(Protocol):
    def get_policy(
        self, transaction: object, *, policy_ref: str,
    ) -> OutputPolicyVersion | None: ...


class PluginOperationRegistryPort(Protocol):
    def get_operation(
        self, transaction: object, *, operation_id: str,
    ) -> PluginOperationCapability | None: ...


class TrustedOutputContextResolver:
    """Compose owner-provided registries into a minimal, fixed context snapshot.

    This class deliberately does not query other modules' ORM, discover current
    versions, contact providers, or execute plugins. Every registry/source port
    must be provided by the caller; missing definitions fail closed.
    """

    def __init__(
        self, *, sources: FixedOutputSourcePort,
        templates: OutputTemplateRegistryPort,
        policies: OutputPolicyRegistryPort,
        operations: PluginOperationRegistryPort,
    ) -> None:
        if any(item is None for item in (sources, templates, policies, operations)):
            raise ValueError("trusted Output resolver ports are required")
        self._sources = sources
        self._templates = templates
        self._policies = policies
        self._operations = operations

    def resolve(
        self, transaction: object, *, actor_id: uuid.UUID,
        command: CreateOutputRequest,
    ) -> ResolvedOutputContext:
        self._validate_command(actor_id, command)
        policy = self._policies.get_policy(
            transaction, policy_ref=command.output_policy_ref)
        template = self._templates.get_immutable_version(
            transaction, template_version_ref=command.template_version_ref)
        operation = self._operations.get_operation(
            transaction, operation_id=command.plugin_operation)
        if not self._valid_policy(policy, command):
            self._reject()
        if not self._valid_template(template, policy, command):
            self._reject()
        if not self._valid_operation(operation, policy, command):
            self._reject()
        if len(command.source_version_refs) > min(policy.max_sources, _MAX_SOURCES):
            self._reject()

        resolved_sources: list[dict[str, object]] = []
        for source_ref in command.source_version_refs:
            source = self._sources.read_authorized_fixed_version(
                transaction, actor_id=actor_id, project_id=command.project_id,
                source_version_ref=source_ref)
            if not self._valid_source(source, policy, template, command, source_ref):
                self._reject()
            allowed_fields = policy.fields_by_source_kind[source.source_kind]
            projected = self._project(source.fields, allowed_fields)
            resolved_sources.append({
                "source_version_ref": str(source.source_version_ref),
                "source_kind": source.source_kind,
                "review_state": source.review_state,
                "fields": projected,
            })

        payload: dict[str, object] = {
            "schema": "output-context.v1",
            "project_id": str(command.project_id),
            "output_type": command.output_type,
            "template_version_ref": str(command.template_version_ref),
            "output_policy_ref": policy.policy_ref,
            "plugin_operation": operation.operation_id,
            "sources": resolved_sources,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > min(policy.max_context_bytes, _MAX_CONTEXT_BYTES):
            self._reject()
        try:
            fingerprint = canonical_payload_fingerprint(payload)
        except IdempotencyError:
            self._reject()
        return ResolvedOutputContext(
            tuple(command.source_version_refs), payload, fingerprint)

    @staticmethod
    def _validate_command(actor_id: uuid.UUID, command: CreateOutputRequest) -> None:
        if (type(actor_id) is not uuid.UUID or not actor_id.int
                or type(command) is not CreateOutputRequest
                or type(command.project_id) is not uuid.UUID or not command.project_id.int
                or type(command.source_version_refs) is not tuple
                or not command.source_version_refs
                or any(type(ref) is not uuid.UUID or not ref.int
                       for ref in command.source_version_refs)
                or len(set(command.source_version_refs)) != len(command.source_version_refs)
                or type(command.template_version_ref) is not uuid.UUID
                or not command.template_version_ref.int
                or type(command.output_type) is not str
                or type(command.output_policy_ref) is not str
                or type(command.plugin_operation) is not str):
            TrustedOutputContextResolver._reject()

    @staticmethod
    def _valid_policy(
        policy: OutputPolicyVersion | None, command: CreateOutputRequest,
    ) -> bool:
        return bool(
            type(policy) is OutputPolicyVersion
            and policy.policy_ref == command.output_policy_ref
            and command.output_type in policy.allowed_output_types
            and command.plugin_operation in policy.allowed_plugin_operations
            and command.template_version_ref in policy.allowed_template_versions
            and 1 <= policy.max_sources <= _MAX_SOURCES
            and 1 <= policy.max_context_bytes <= _MAX_CONTEXT_BYTES
            and bool(policy.allowed_review_states)
            and isinstance(policy.fields_by_source_kind, Mapping)
        )

    @staticmethod
    def _valid_template(
        template: OutputTemplateVersion | None,
        policy: OutputPolicyVersion,
        command: CreateOutputRequest,
    ) -> bool:
        return bool(
            type(template) is OutputTemplateVersion
            and template.template_version_ref == command.template_version_ref
            and template.immutable is True
            and template.published is True
            and template.output_type == command.output_type
            and template.output_type in policy.allowed_output_types
            and bool(template.source_kinds)
        )

    @staticmethod
    def _valid_operation(
        operation: PluginOperationCapability | None,
        policy: OutputPolicyVersion,
        command: CreateOutputRequest,
    ) -> bool:
        return bool(
            type(operation) is PluginOperationCapability
            and operation.operation_id == command.plugin_operation
            and operation.enabled is True
            and operation.trusted is True
            and command.output_type in operation.output_types
        )

    @staticmethod
    def _valid_source(
        source: FixedSourceVersion | None, policy: OutputPolicyVersion,
        template: OutputTemplateVersion, command: CreateOutputRequest,
        expected_ref: uuid.UUID,
    ) -> bool:
        return bool(
            type(source) is FixedSourceVersion
            and source.authorized is True
            and source.project_id == command.project_id
            and source.source_version_ref == expected_ref
            and source.source_kind in template.source_kinds
            and source.source_kind in policy.fields_by_source_kind
            and source.review_state in policy.allowed_review_states
            and isinstance(source.fields, Mapping)
        )

    @classmethod
    def _project(
        cls, fields: Mapping[str, object], allowed_names: tuple[str, ...],
    ) -> dict[str, object]:
        if (type(allowed_names) is not tuple
                or any(type(name) is not str or not name for name in allowed_names)
                or len(set(allowed_names)) != len(allowed_names)):
            cls._reject()
        projected: dict[str, object] = {}
        for name in allowed_names:
            if name in fields:
                projected[name] = cls._json_value(fields[name])
        return projected

    @classmethod
    def _json_value(cls, value: object, depth: int = 0) -> object:
        if depth > 8:
            cls._reject()
        if type(value) in _ALLOWED_JSON_TYPES:
            if type(value) is str and len(value) > 32_768:
                cls._reject()
            if type(value) is float and (value != value or abs(value) == float("inf")):
                cls._reject()
            return value
        if type(value) is list and len(value) <= 512:
            return [cls._json_value(item, depth + 1) for item in value]
        if type(value) is dict and len(value) <= 128:
            if any(type(key) is not str or not key or len(key) > 128 for key in value):
                cls._reject()
            return {key: cls._json_value(item, depth + 1)
                    for key, item in sorted(value.items())}
        cls._reject()

    @staticmethod
    def _reject() -> None:
        raise OutputRequestError("VALIDATION_FAILED")
