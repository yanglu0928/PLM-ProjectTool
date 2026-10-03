"""AI-owned Prompt/parameter content projection and strict renderer."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    ResolvedAITaskSubmissionPolicy,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import (
    PromptVersionDraft,
    PromptVersionError,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_PARAMETER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_TOKEN = re.compile(r"\{(input|context|parameters)\}")
_UNSAFE_FORMAT = {"Cf", "Cs", "Co", "Cn"}
_RENDERING_POLICY = ("strict-placeholders.v1", 1)


class AIExecutionPromptContentError(RuntimeError):
    def __init__(self, code: str = "AI_EXECUTION_PROMPT_CONTENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


def _canonical_runtime_text(value: object, *, required: bool,
                            max_bytes: int) -> str:
    if type(value) is not str:
        raise AIExecutionPromptContentError("AI_EXECUTION_PROMPT_RENDER_INVALID")
    normalized = unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n"),
    )
    if (required and not normalized.strip()
            or len(normalized.encode("utf-8")) > max_bytes
            or any((ord(char) < 32 and char not in "\n\t")
                   or unicodedata.category(char) in _UNSAFE_FORMAT
                   for char in normalized)):
        raise AIExecutionPromptContentError("AI_EXECUTION_PROMPT_RENDER_INVALID")
    return normalized


def _canonical_parameters(parameters: Mapping[str, object]) -> str:
    normalized: dict[str, object] = {}
    for key, value in parameters.items():
        if type(value) is str:
            normalized[key] = _canonical_runtime_text(
                value, required=True, max_bytes=16_384,
            )
        else:
            normalized[key] = value
    try:
        encoded = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError):
        raise AIExecutionPromptContentError() from None
    if len(encoded.encode("utf-8")) > 16_384:
        raise AIExecutionPromptContentError()
    return encoded


@dataclass(frozen=True, slots=True)
class AIExecutionPromptTaskContent:
    """Short-lived AI Owner value; sensitive fields are excluded from repr."""

    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    task_type: str
    prompt_policy_ref: str
    prompt_policy_version: int
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    system_template: str = field(repr=False)
    user_template: str = field(repr=False)
    system_template_hash: str
    user_template_hash: str
    provider_policy_ref: str
    output_schema_ref: str
    schema_version: int
    context_policy_ref: str
    task_parameters: Mapping[str, object] = field(repr=False)
    task_parameters_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        identifiers = (
            self.ai_task_id, self.project_id, self.job_id,
            self.requested_by, self.trace_id, self.prompt_template_id,
        )
        refs = (
            self.prompt_policy_ref, self.provider_policy_ref,
            self.output_schema_ref, self.context_policy_ref,
        )
        if (not all(_id(value) for value in identifiers)
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in refs)
                or type(self.prompt_policy_version) is not int
                or not 1 <= self.prompt_policy_version <= 2_147_483_647
                or type(self.prompt_version_no) is not int
                or not 1 <= self.prompt_version_no <= 9_223_372_036_854_775_807
                or type(self.schema_version) is not int
                or not 1 <= self.schema_version <= 2_147_483_647
                or not _digest(self.task_parameters_fingerprint)
                or not isinstance(self.task_parameters, Mapping)
                or len(self.task_parameters) > 16):
            raise AIExecutionPromptContentError()
        try:
            task_type = PromptTaskType(self.task_type)
            draft = PromptVersionDraft(
                self.prompt_template_id, task_type, self.system_template,
                self.user_template, self.output_schema_ref, self.schema_version,
                self.context_policy_ref, self.provider_policy_ref,
            )
        except (ValueError, PromptVersionError):
            raise AIExecutionPromptContentError() from None
        if (draft.system_hash != self.system_template_hash
                or draft.user_hash != self.user_template_hash
                or draft.system_template != self.system_template
                or draft.user_template != self.user_template):
            raise AIExecutionPromptContentError()
        copied: dict[str, object] = {}
        for key, value in self.task_parameters.items():
            if (type(key) is not str or _PARAMETER.fullmatch(key) is None
                    or type(value) is str and (
                        not value or value != value.strip() or len(value) > 4096)
                    or type(value) is int and not isinstance(value, bool) and not (
                        -9_223_372_036_854_775_808
                        <= value <= 9_223_372_036_854_775_807)
                    or type(value) not in (str, int, bool)):
                raise AIExecutionPromptContentError()
            copied[key] = value
        _canonical_parameters(copied)
        object.__setattr__(self, "task_parameters", MappingProxyType(copied))

    @property
    def canonical_parameters_json(self) -> str:
        return _canonical_parameters(self.task_parameters)


@dataclass(frozen=True, slots=True)
class AIExecutionPromptPlanningContent:
    """Short-lived active Prompt projection used before an AI Task exists."""

    task_type: str
    prompt_policy_ref: str
    prompt_policy_version: int
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    system_template: str = field(repr=False)
    user_template: str = field(repr=False)
    system_template_hash: str
    user_template_hash: str
    provider_policy_ref: str
    output_schema_ref: str
    schema_version: int
    context_policy_ref: str
    task_parameters: Mapping[str, object] = field(repr=False)
    task_parameters_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        refs = (
            self.prompt_policy_ref, self.provider_policy_ref,
            self.output_schema_ref, self.context_policy_ref,
        )
        if (not _id(self.prompt_template_id)
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in refs)
                or type(self.prompt_policy_version) is not int
                or not 1 <= self.prompt_policy_version <= 2_147_483_647
                or type(self.prompt_version_no) is not int
                or not 1 <= self.prompt_version_no <= 9_223_372_036_854_775_807
                or type(self.schema_version) is not int
                or not 1 <= self.schema_version <= 2_147_483_647
                or not _digest(self.task_parameters_fingerprint)
                or not isinstance(self.task_parameters, Mapping)
                or len(self.task_parameters) > 16):
            raise AIExecutionPromptContentError()
        try:
            task_type = PromptTaskType(self.task_type)
            draft = PromptVersionDraft(
                self.prompt_template_id, task_type, self.system_template,
                self.user_template, self.output_schema_ref, self.schema_version,
                self.context_policy_ref, self.provider_policy_ref,
            )
        except (ValueError, PromptVersionError):
            raise AIExecutionPromptContentError() from None
        if (draft.system_hash != self.system_template_hash
                or draft.user_hash != self.user_template_hash
                or draft.system_template != self.system_template
                or draft.user_template != self.user_template):
            raise AIExecutionPromptContentError()
        copied: dict[str, object] = {}
        for key, value in self.task_parameters.items():
            if (type(key) is not str or _PARAMETER.fullmatch(key) is None
                    or type(value) is str and (
                        not value or value != value.strip() or len(value) > 4096)
                    or type(value) is int and not isinstance(value, bool) and not (
                        -9_223_372_036_854_775_808
                        <= value <= 9_223_372_036_854_775_807)
                    or type(value) not in (str, int, bool)):
                raise AIExecutionPromptContentError()
            copied[key] = value
        _canonical_parameters(copied)
        object.__setattr__(self, "task_parameters", MappingProxyType(copied))

    @property
    def canonical_parameters_json(self) -> str:
        return _canonical_parameters(self.task_parameters)


class AIExecutionPromptPlanningRepositoryPort(Protocol):
    def load_current(
        self, transaction: object, *, policy: ResolvedAITaskSubmissionPolicy,
    ) -> AIExecutionPromptPlanningContent | None: ...


class AIExecutionPromptPlanningOwner:
    def __init__(self, repository: AIExecutionPromptPlanningRepositoryPort) -> None:
        if repository is None:
            raise ValueError("AI execution planning Prompt repository required")
        self._repository = repository

    def resolve_current(
        self, transaction: object, *, policy: ResolvedAITaskSubmissionPolicy,
    ) -> AIExecutionPromptPlanningContent:
        if transaction is None or type(policy) is not ResolvedAITaskSubmissionPolicy:
            raise AIExecutionPromptContentError()
        try:
            content = self._repository.load_current(transaction, policy=policy)
        except AIExecutionPromptContentError:
            raise
        except Exception:
            raise AIExecutionPromptContentError() from None
        if (type(content) is not AIExecutionPromptPlanningContent
                or content.task_type != policy.task_type
                or content.prompt_policy_ref != policy.reference
                or content.prompt_policy_version != policy.policy_version
                or content.prompt_template_id != policy.prompt_template_id
                or content.output_schema_ref != policy.output_schema_ref
                or content.context_policy_ref != policy.context_policy_ref):
            raise AIExecutionPromptContentError()
        content.__post_init__()
        return content


class AIExecutionPromptTaskContentRepositoryPort(Protocol):
    def load_exact(
        self,
        transaction: object,
        *,
        grant: AITaskExecutionGrant,
    ) -> AIExecutionPromptTaskContent | None: ...


class AIExecutionPromptTaskContentOwner:
    def __init__(self, repository: AIExecutionPromptTaskContentRepositoryPort) -> None:
        if repository is None:
            raise ValueError("AI execution Prompt content repository required")
        self._repository = repository

    def load_exact(self, transaction: object, *,
                   grant: AITaskExecutionGrant) -> AIExecutionPromptTaskContent:
        if transaction is None or type(grant) is not AITaskExecutionGrant:
            raise AIExecutionPromptContentError()
        grant.__post_init__()
        try:
            content = self._repository.load_exact(transaction, grant=grant)
        except AIExecutionPromptContentError:
            raise
        except Exception:
            raise AIExecutionPromptContentError() from None
        if (type(content) is not AIExecutionPromptTaskContent
                or content.ai_task_id != grant.ai_task_id
                or content.project_id != grant.project_id
                or content.job_id != grant.job_id
                or content.requested_by != grant.requested_by
                or content.trace_id != grant.trace_id
                or content.task_type != grant.task_type
                or content.prompt_policy_ref != grant.prompt_policy_ref
                or content.prompt_policy_version != grant.prompt_policy_version
                or content.prompt_template_id != grant.prompt_template_id
                or content.prompt_version_no != grant.prompt_version_no
                or content.system_template_hash != grant.system_template_hash
                or content.user_template_hash != grant.user_template_hash
                or content.provider_policy_ref != grant.provider_policy_ref
                or content.output_schema_ref != grant.output_schema_ref
                or content.schema_version != grant.schema_version
                or content.context_policy_ref != grant.context_policy_ref
                or content.task_parameters_fingerprint
                   != grant.task_parameters_fingerprint):
            raise AIExecutionPromptContentError()
        content.__post_init__()
        return content


@dataclass(frozen=True, slots=True)
class RenderedAIExecutionPrompt:
    content_plan_id: uuid.UUID
    rendering_policy_ref: str
    rendering_policy_version: int
    system_utf8: bytes = field(repr=False)
    user_utf8: bytes = field(repr=False)
    parameters_utf8: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (not _id(self.content_plan_id)
                or (self.rendering_policy_ref, self.rendering_policy_version)
                   != _RENDERING_POLICY
                or any(type(value) is not bytes or not value
                       or len(value) > 1_073_741_824
                       for value in (
                           self.system_utf8, self.user_utf8,
                           self.parameters_utf8,
                       ))):
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_RENDER_INVALID",
            )

    @property
    def fingerprint(self) -> bytes:
        return canonical_payload_fingerprint({
            "content_plan_id": str(self.content_plan_id),
            "rendering_policy_ref": self.rendering_policy_ref,
            "rendering_policy_version": self.rendering_policy_version,
            "system_utf8": self.system_utf8.hex(),
            "user_utf8": self.user_utf8.hex(),
            "parameters_utf8": self.parameters_utf8.hex(),
        })


class StrictAIExecutionPromptRenderer:
    """Render only three literal placeholders; never evaluate expressions."""

    def render(
        self,
        plan: AIExecutionContentPlan,
        content: AIExecutionPromptTaskContent | AIExecutionPromptPlanningContent,
        *,
        input_text: str,
        context_text: str | None,
    ) -> RenderedAIExecutionPrompt:
        if (type(plan) is not AIExecutionContentPlan
                or type(content) not in (
                    AIExecutionPromptTaskContent,
                    AIExecutionPromptPlanningContent,
                )):
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_RENDER_INVALID",
            )
        plan.__post_init__()
        content.__post_init__()
        if (plan.prompt.rendering_policy_ref,
                plan.prompt.rendering_policy_version) != _RENDERING_POLICY:
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_RENDER_UNSUPPORTED",
            )
        if (content.prompt_policy_ref != plan.prompt.prompt_policy_ref
                or content.prompt_policy_version
                   != plan.prompt.prompt_policy_version
                or content.prompt_template_id != plan.prompt.prompt_template_id
                or content.prompt_version_no != plan.prompt.prompt_version_no
                or content.system_template_hash
                   != plan.prompt.system_template_hash
                or content.user_template_hash != plan.prompt.user_template_hash
                or content.provider_policy_ref
                   != plan.prompt.provider_policy_ref
                or content.output_schema_ref != plan.prompt.output_schema_ref
                or content.schema_version != plan.prompt.schema_version
                or content.context_policy_ref != plan.context.context_policy_ref
                or content.task_parameters_fingerprint
                   != plan.task_parameters_fingerprint):
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_CONTENT_MISMATCH",
            )
        input_value = _canonical_runtime_text(
            input_text, required=True, max_bytes=100_000_000,
        )
        if plan.context.mode == "RAG_CONTEXT":
            context_value = _canonical_runtime_text(
                context_text, required=True, max_bytes=100_000_000,
            )
        elif plan.context.mode == "NONE" and context_text is None:
            context_value = ""
        else:
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_RENDER_INVALID",
            )
        parameters_value = content.canonical_parameters_json
        templates = (content.system_template, content.user_template)
        counts = {name: sum(template.count("{" + name + "}")
                            for template in templates)
                  for name in ("input", "context", "parameters")}
        if (counts["input"] != 1
                or plan.context.mode == "RAG_CONTEXT"
                and counts["context"] != 1
                or plan.context.mode == "NONE" and counts["context"] > 1
                or content.task_parameters and counts["parameters"] != 1
                or not content.task_parameters and counts["parameters"] > 1
                or any(_has_unknown_or_stray_brace(template)
                       for template in templates)):
            raise AIExecutionPromptContentError(
                "AI_EXECUTION_PROMPT_TEMPLATE_INVALID",
            )
        replacements = {
            "input": input_value,
            "context": context_value,
            "parameters": parameters_value,
        }
        rendered = tuple(_TOKEN.sub(
            lambda match: replacements[match.group(1)], template,
        ) for template in templates)
        system_utf8, user_utf8 = (value.encode("utf-8") for value in rendered)
        return RenderedAIExecutionPrompt(
            plan.content_plan_id, _RENDERING_POLICY[0], _RENDERING_POLICY[1],
            system_utf8, user_utf8, parameters_value.encode("utf-8"),
        )


def _has_unknown_or_stray_brace(template: str) -> bool:
    without_tokens = _TOKEN.sub("", template)
    return "{" in without_tokens or "}" in without_tokens
