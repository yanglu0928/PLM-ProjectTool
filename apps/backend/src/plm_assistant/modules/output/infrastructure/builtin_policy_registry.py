"""Read-only, fixed-version policy registry for the built-in Output flow."""

from __future__ import annotations

import uuid
from types import MappingProxyType
from typing import Mapping

from plm_assistant.modules.output.application.resolve_context import (
    OutputPolicyVersion,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
)

BUILTIN_REQUIREMENT_DOCX_POLICY_REF = "output.policy.requirement-docx.v1"

_BUILTIN_POLICIES = (
    OutputPolicyVersion(
        policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF,
        allowed_template_versions=(
            BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
        ),
        allowed_output_types=("DOCX",),
        allowed_plugin_operations=("word.generate",),
        allowed_review_states=("APPROVED",),
        fields_by_source_kind=MappingProxyType({
            "REQUIREMENT_VERSION": (
                "title", "statement", "acceptance_criteria",
            ),
        }),
        max_sources=4,
        max_context_bytes=8192,
    ),
)


class BuiltinOutputPolicyRegistry:
    """Resolve the narrow built-in policy without database or mutable config.

    Allowing an operation in a policy is not evidence that the plugin operation
    is installed, enabled, or trusted. The resolver must verify that separately.
    """

    def __init__(
        self, entries: tuple[OutputPolicyVersion, ...] | None = None,
    ) -> None:
        values = _BUILTIN_POLICIES if entries is None else entries
        if type(values) is not tuple:
            raise ValueError("builtin output policy catalog is invalid")
        catalog: dict[str, OutputPolicyVersion] = {}
        for item in values:
            if not self._valid(item) or item.policy_ref in catalog:
                raise ValueError("builtin output policy catalog is invalid")
            catalog[item.policy_ref] = item
        if not catalog:
            raise ValueError("builtin output policy catalog is empty")
        self._catalog: Mapping[str, OutputPolicyVersion] = (
            MappingProxyType(catalog)
        )

    @staticmethod
    def _valid(item: object) -> bool:
        return bool(
            type(item) is OutputPolicyVersion
            and type(item.policy_ref) is str and item.policy_ref
            and type(item.allowed_template_versions) is tuple
            and bool(item.allowed_template_versions)
            and all(type(ref) is uuid.UUID and ref.int
                    for ref in item.allowed_template_versions)
            and len(set(item.allowed_template_versions))
                == len(item.allowed_template_versions)
            and type(item.allowed_output_types) is tuple
            and item.allowed_output_types == ("DOCX",)
            and type(item.allowed_plugin_operations) is tuple
            and item.allowed_plugin_operations == ("word.generate",)
            and type(item.allowed_review_states) is tuple
            and item.allowed_review_states == ("APPROVED",)
            and isinstance(item.fields_by_source_kind, Mapping)
            and dict(item.fields_by_source_kind) == {
                "REQUIREMENT_VERSION": (
                    "title", "statement", "acceptance_criteria",
                ),
            }
            and type(item.max_sources) is int and 1 <= item.max_sources <= 4
            and type(item.max_context_bytes) is int
            and 256 <= item.max_context_bytes <= 8192
        )

    def get_policy(
        self, transaction: object, *, policy_ref: str,
    ) -> OutputPolicyVersion | None:
        del transaction  # Static package data; the port keeps transaction shape.
        if type(policy_ref) is not str or not policy_ref:
            return None
        return self._catalog.get(policy_ref)
