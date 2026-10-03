"""Deterministic provider-neutral AI execution envelope.

The builder performs no network or retrieval I/O.  Only explicitly registered
context and token-estimation policies are accepted.  Provider adapters may map
this logical envelope later, but may not change its semantic content silently.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentProjection,
    content_plan_fingerprint,
    require_content_plan_for_grant,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningContent, AIExecutionPromptTaskContent,
    RenderedAIExecutionPrompt,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskPayloadPlanProof,
    AITaskExecutionGrant,
    execution_grant_fingerprint,
    require_payload_plan,
)


_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_ENCODING = ("provider-neutral-json.v1", 1)
_MAX_ENVELOPE_BYTES = 100_000_000


class AIExecutionEnvelopeError(RuntimeError):
    def __init__(self, code: str = "AI_EXECUTION_ENVELOPE_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


@dataclass(frozen=True, slots=True)
class AIExecutionTokenEstimate:
    estimator_ref: str
    estimator_version: int
    provider_model_key: str
    model_revision: str
    input_tokens: int

    def __post_init__(self) -> None:
        if (type(self.estimator_ref) is not str
                or _REF.fullmatch(self.estimator_ref) is None
                or type(self.estimator_version) is not int
                or not 1 <= self.estimator_version <= 2_147_483_647
                or type(self.provider_model_key) is not str
                or _REF.fullmatch(self.provider_model_key) is None
                or type(self.model_revision) is not str
                or _REF.fullmatch(self.model_revision) is None
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_073_741_824):
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_TOKEN_ESTIMATE_INVALID")


class AIExecutionTokenEstimatorPort(Protocol):
    estimator_ref: str
    estimator_version: int

    def estimate(
        self, *, provider_model_key: str, model_revision: str,
        system_utf8: bytes, user_utf8: bytes,
    ) -> AIExecutionTokenEstimate: ...


class Utf8ByteUpperBoundTokenEstimator:
    """Conservative deterministic estimator; requires adapter eligibility proof.

    It is not claimed to be a universal provider tokenizer.  Deployment policy
    may bind it only to a model whose tokenizer and chat overhead were verified
    not to exceed one token per UTF-8 byte plus this fixed overhead.
    """

    estimator_ref = "utf8-byte-upper-bound.v1"
    estimator_version = 1

    def estimate(
        self, *, provider_model_key: str, model_revision: str,
        system_utf8: bytes, user_utf8: bytes,
    ) -> AIExecutionTokenEstimate:
        if (type(system_utf8) is not bytes or not system_utf8
                or type(user_utf8) is not bytes or not user_utf8):
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_TOKEN_ESTIMATE_INVALID")
        count = len(system_utf8) + len(user_utf8) + 16
        return AIExecutionTokenEstimate(
            self.estimator_ref, self.estimator_version,
            provider_model_key, model_revision, count,
        )


class AIExecutionTokenEstimatorRegistry:
    def __init__(self, estimators: tuple[AIExecutionTokenEstimatorPort, ...]) -> None:
        values: dict[tuple[str, int], AIExecutionTokenEstimatorPort] = {}
        if type(estimators) is not tuple or not estimators:
            raise ValueError("AI execution token estimators required")
        for estimator in estimators:
            ref = getattr(estimator, "estimator_ref", None)
            version = getattr(estimator, "estimator_version", None)
            key = (ref, version)
            if (type(ref) is not str or _REF.fullmatch(ref) is None
                    or type(version) is not int or version < 1
                    or key in values or not callable(
                        getattr(estimator, "estimate", None))):
                raise ValueError("invalid or duplicate AI token estimator")
            values[key] = estimator
        self._estimators = values

    def estimate(
        self, plan: AIExecutionContentPlan,
        rendered: RenderedAIExecutionPrompt,
    ) -> AIExecutionTokenEstimate:
        estimator = self._estimators.get((
            plan.token_estimator_ref, plan.token_estimator_version,
        ))
        if estimator is None:
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_TOKEN_ESTIMATOR_UNSUPPORTED")
        try:
            result = estimator.estimate(
                provider_model_key=plan.provider_model_key,
                model_revision=plan.model_revision,
                system_utf8=rendered.system_utf8,
                user_utf8=rendered.user_utf8,
            )
        except AIExecutionEnvelopeError:
            raise
        except Exception:
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_TOKEN_ESTIMATE_INVALID") from None
        if (type(result) is not AIExecutionTokenEstimate
                or result.estimator_ref != plan.token_estimator_ref
                or result.estimator_version != plan.token_estimator_version
                or result.provider_model_key != plan.provider_model_key
                or result.model_revision != plan.model_revision):
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_TOKEN_ESTIMATE_INVALID")
        result.__post_init__()
        return result


class AIExecutionContextPolicyRegistry:
    """Current explicit context boundary; RAG remains closed until its Owner exists."""

    def __init__(self, no_retrieval_policy_refs: frozenset[str]) -> None:
        if (type(no_retrieval_policy_refs) is not frozenset
                or not no_retrieval_policy_refs
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in no_retrieval_policy_refs)):
            raise ValueError("explicit no-retrieval policies required")
        self._no_retrieval = no_retrieval_policy_refs

    def resolve(self, plan: AIExecutionContentPlan) -> str | None:
        if (plan.context.mode == "NONE"
                and plan.context.context_policy_ref in self._no_retrieval):
            return None
        # RAG_CONTEXT is deliberately not accepted from caller-supplied text.
        # It needs a future immutable RetrievalRun/ContextBundle Owner.
        raise AIExecutionEnvelopeError(
            "AI_EXECUTION_CONTEXT_POLICY_UNSUPPORTED")


@dataclass(frozen=True, slots=True)
class AIExecutionEnvelope:
    content_plan_id: uuid.UUID
    content_plan_fingerprint: bytes = field(repr=False)
    encoding_ref: str
    encoding_version: int
    source_projection_fingerprints: tuple[bytes, ...] = field(repr=False)
    canonical_bytes: bytes = field(repr=False)
    record_count: int
    input_tokens: int
    token_estimator_ref: str
    token_estimator_version: int
    context_bundle_fingerprint: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (not _id(self.content_plan_id)
                or not _digest(self.content_plan_fingerprint)
                or (self.encoding_ref, self.encoding_version) != _ENCODING
                or type(self.source_projection_fingerprints) is not tuple
                or not self.source_projection_fingerprints
                or any(not _digest(value)
                       for value in self.source_projection_fingerprints)
                or type(self.canonical_bytes) is not bytes
                or not 1 <= len(self.canonical_bytes) <= _MAX_ENVELOPE_BYTES
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 1_000_000_000
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_073_741_824
                or type(self.token_estimator_ref) is not str
                or _REF.fullmatch(self.token_estimator_ref) is None
                or type(self.token_estimator_version) is not int
                or self.token_estimator_version < 1
                or (self.context_bundle_fingerprint is not None
                    and not _digest(self.context_bundle_fingerprint))):
            raise AIExecutionEnvelopeError()
        try:
            payload = json.loads(
                self.canonical_bytes.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            raise AIExecutionEnvelopeError() from None
        if _canonical_json(payload) != self.canonical_bytes:
            raise AIExecutionEnvelopeError()

    @property
    def payload_fingerprint(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes).digest()

    @property
    def payload_bytes(self) -> int:
        return len(self.canonical_bytes)


class AIExecutionEnvelopeBuilder:
    def __init__(
        self, *, renderer: StrictAIExecutionPromptRenderer,
        context_policies: AIExecutionContextPolicyRegistry,
        token_estimators: AIExecutionTokenEstimatorRegistry,
    ) -> None:
        if any(value is None for value in (
                renderer, context_policies, token_estimators)):
            raise ValueError("AI execution envelope dependencies required")
        self._renderer = renderer
        self._contexts = context_policies
        self._estimators = token_estimators

    def build(
        self, *, plan: AIExecutionContentPlan,
        sources: tuple[AIExecutionContentProjection, ...],
        prompt_content: AIExecutionPromptTaskContent | AIExecutionPromptPlanningContent,
    ) -> AIExecutionEnvelope:
        if (type(plan) is not AIExecutionContentPlan
                or type(sources) is not tuple
                or len(sources) != len(plan.sources)
                or type(prompt_content) not in (
                    AIExecutionPromptTaskContent,
                    AIExecutionPromptPlanningContent,
                )):
            raise AIExecutionEnvelopeError()
        plan.__post_init__()
        projected: list[object] = []
        projection_hashes: list[bytes] = []
        projected_bytes = 0
        for planned, source in zip(plan.sources, sources, strict=True):
            if (type(source) is not AIExecutionContentProjection
                    or source.source != planned):
                raise AIExecutionEnvelopeError(
                    "AI_EXECUTION_SOURCE_PROJECTION_MISMATCH")
            try:
                source.__post_init__()
                value = json.loads(
                    source.content_utf8.decode("utf-8"),
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_constant,
                )
            except Exception:
                raise AIExecutionEnvelopeError(
                    "AI_EXECUTION_SOURCE_PROJECTION_INVALID") from None
            if _canonical_json(value) != source.content_utf8:
                raise AIExecutionEnvelopeError(
                    "AI_EXECUTION_SOURCE_PROJECTION_INVALID")
            projected_bytes += len(source.content_utf8)
            if projected_bytes > _MAX_ENVELOPE_BYTES:
                raise AIExecutionEnvelopeError(
                    "AI_EXECUTION_ENVELOPE_LIMIT_EXCEEDED")
            projected.append(value)
            projection_hashes.append(source.projection_fingerprint)
        input_bundle = _canonical_json({
            "schema_version": "ai-input-bundle.v1",
            "sources": projected,
        }).decode("utf-8")
        context_text = self._contexts.resolve(plan)
        try:
            rendered = self._renderer.render(
                plan, prompt_content, input_text=input_bundle,
                context_text=context_text,
            )
        except Exception:
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_PROMPT_RENDER_FAILED") from None
        estimate = self._estimators.estimate(plan, rendered)
        try:
            system = rendered.system_utf8.decode("utf-8")
            user = rendered.user_utf8.decode("utf-8")
        except UnicodeDecodeError:
            raise AIExecutionEnvelopeError() from None
        canonical = _canonical_json({
            "messages": (
                {"content": system, "role": "system"},
                {"content": user, "role": "user"},
            ),
            "model": {"key": plan.provider_model_key,
                      "revision": plan.model_revision},
            "response_format": {
                "schema_ref": plan.prompt.output_schema_ref,
                "schema_version": plan.prompt.schema_version,
                "type": "structured_json",
            },
            "schema_version": "provider-neutral-chat.v1",
        })
        record_count = sum(source.record_count for source in plan.sources)
        record_count += plan.context.record_count
        return AIExecutionEnvelope(
            plan.content_plan_id, content_plan_fingerprint(plan),
            plan.envelope_encoding_ref, plan.envelope_encoding_version,
            tuple(projection_hashes), canonical, record_count,
            estimate.input_tokens, estimate.estimator_ref,
            estimate.estimator_version,
            plan.context.context_bundle_fingerprint,
        )


def require_envelope_for_grant(
    grant: AITaskExecutionGrant,
    plan: AIExecutionContentPlan,
    envelope: AIExecutionEnvelope,
    *, now: datetime,
) -> AITaskPayloadPlanProof:
    if (type(grant) is not AITaskExecutionGrant
            or type(plan) is not AIExecutionContentPlan
            or type(envelope) is not AIExecutionEnvelope):
        raise AIExecutionEnvelopeError(
            "AI_EXECUTION_ENVELOPE_NOT_AUTHORIZED")
    try:
        require_content_plan_for_grant(grant, plan)
        envelope.__post_init__()
        expected_projection_hashes = tuple(
            source.projection_fingerprint for source in plan.sources)
        if (envelope.content_plan_id != plan.content_plan_id
                or not hmac.compare_digest(
                    envelope.content_plan_fingerprint,
                    content_plan_fingerprint(plan))
                or envelope.source_projection_fingerprints
                   != expected_projection_hashes
                or (envelope.encoding_ref, envelope.encoding_version)
                   != (plan.envelope_encoding_ref,
                       plan.envelope_encoding_version)
                or (envelope.token_estimator_ref,
                    envelope.token_estimator_version)
                   != (plan.token_estimator_ref,
                       plan.token_estimator_version)):
            raise AIExecutionEnvelopeError(
                "AI_EXECUTION_ENVELOPE_NOT_AUTHORIZED")
        proof = AITaskPayloadPlanProof(
            grant.ai_task_id, grant.job_id, grant.attempt_no,
            execution_grant_fingerprint(grant),
            grant.source_refs_fingerprint, envelope.payload_fingerprint,
            envelope.record_count, envelope.payload_bytes,
            envelope.input_tokens, envelope.context_bundle_fingerprint,
        )
        return require_payload_plan(grant, proof, now=now)
    except AIExecutionEnvelopeError:
        raise
    except Exception:
        raise AIExecutionEnvelopeError(
            "AI_EXECUTION_ENVELOPE_NOT_AUTHORIZED") from None


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise AIExecutionEnvelopeError() from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError("non-finite JSON number")
