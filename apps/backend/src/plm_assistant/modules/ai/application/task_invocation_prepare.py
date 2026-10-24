"""Prepare exact AI request bytes before atomically beginning an Invocation."""

from __future__ import annotations

import hmac
import json
import unicodedata
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .execution_content_plan import (
    AIExecutionContentProjection,
    AIExecutionContentReadOwnerPort,
    AIExecutionContentReadQuery,
    AIExecutionContentSourceIdentity,
    require_content_plan_for_grant,
)
from .execution_content_plan_owner import AIExecutionContentPlanOwner
from .execution_envelope import (
    AIExecutionEnvelope,
    AIExecutionEnvelopeBuilder,
    require_envelope_for_grant,
)
from .execution_prompt_content import AIExecutionPromptTaskContentOwner
from .task_execution_grant import AITaskExecutionGrant, AITaskPayloadPlanProof
from .task_execution_grant_service import AITaskExecutionGrantIssuer


class AITaskInvocationPrepareError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_INVOCATION_NOT_PREPARED") -> None:
        self.code = code
        super().__init__(code)


class _ReadOwner(Protocol):
    def read_exact(
        self, transaction: object, query: AIExecutionContentReadQuery,
        source: AIExecutionContentSourceIdentity,
    ) -> AIExecutionContentProjection: ...


class _ContextReadOwner(Protocol):
    def read_exact(
        self, transaction: object, query: AIExecutionContentReadQuery,
        context: object,
    ) -> str: ...


def _safe_node_id(value: object) -> bool:
    if (type(value) is not str or not value or len(value) > 256
            or value != value.strip()
            or unicodedata.normalize("NFC", value) != value):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return False
    return (len(encoded) <= 512
            and not any(unicodedata.category(char) in {"Cc", "Cs"}
                        for char in value))


@dataclass(frozen=True, slots=True)
class AIExecutionSourceNodeCatalog:
    """No-content node identities that the Provider actually received."""

    source_ordinal: int
    node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.source_ordinal) is not int
                or not 1 <= self.source_ordinal <= 1000
                or type(self.node_ids) is not tuple or not self.node_ids
                or len(self.node_ids) > 1_000_000
                or any(not _safe_node_id(value) for value in self.node_ids)
                or len(set(self.node_ids)) != len(self.node_ids)):
            raise AITaskInvocationPrepareError()


@dataclass(frozen=True, slots=True)
class PreparedAITaskInvocation:
    """Short-lived sensitive bytes plus their no-content authorization proof."""

    grant: AITaskExecutionGrant
    envelope: AIExecutionEnvelope = field(repr=False)
    payload_plan: AITaskPayloadPlanProof
    source_node_catalogs: tuple[AIExecutionSourceNodeCatalog, ...] = field(
        default=(), repr=False,
    )

    def __post_init__(self) -> None:
        if (type(self.grant) is not AITaskExecutionGrant
                or type(self.envelope) is not AIExecutionEnvelope
                or type(self.payload_plan) is not AITaskPayloadPlanProof
                or type(self.source_node_catalogs) is not tuple):
            raise AITaskInvocationPrepareError()
        self.grant.__post_init__()
        self.envelope.__post_init__()
        self.payload_plan.__post_init__()
        if self.source_node_catalogs:
            if (len(self.source_node_catalogs) != len(self.grant.input_refs)
                    or any(type(item) is not AIExecutionSourceNodeCatalog
                           for item in self.source_node_catalogs)):
                raise AITaskInvocationPrepareError()
            for item, input_ref in zip(
                    self.source_node_catalogs, self.grant.input_refs, strict=True):
                item.__post_init__()
                if item.source_ordinal != input_ref.ordinal:
                    raise AITaskInvocationPrepareError()


def _source_node_catalogs(
    projected: tuple[AIExecutionContentProjection, ...],
) -> tuple[AIExecutionSourceNodeCatalog, ...]:
    result: list[AIExecutionSourceNodeCatalog] = []
    for projection in projected:
        try:
            payload = json.loads(projection.content_utf8.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            raise AITaskInvocationPrepareError() from None
        if (type(payload) is not dict
                or payload.get("schema_version") != "document-minimum-text-v1"
                or type(payload.get("nodes")) is not list
                or not payload["nodes"]):
            raise AITaskInvocationPrepareError()
        node_ids: list[str] = []
        for node in payload["nodes"]:
            if type(node) is not dict or not _safe_node_id(node.get("node_id")):
                raise AITaskInvocationPrepareError()
            node_ids.append(node["node_id"])
        result.append(AIExecutionSourceNodeCatalog(
            projection.source.ordinal, tuple(node_ids),
        ))
    return tuple(result)


class AITaskInvocationPrepareService:
    """Read immutable content in one short transaction; perform no provider I/O."""

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        grants: AITaskExecutionGrantIssuer,
        plans: AIExecutionContentPlanOwner,
        prompts: AIExecutionPromptTaskContentOwner,
        source_owners: Mapping[str, AIExecutionContentReadOwnerPort],
        envelopes: AIExecutionEnvelopeBuilder,
        context_owners: Mapping[str, _ContextReadOwner] | None = None,
    ) -> None:
        if (any(value is None for value in (
                unit_of_work, grants, plans, prompts, envelopes))
                or not isinstance(source_owners, Mapping) or not source_owners
                or any(type(key) is not str or not key or owner is None
                       or not callable(getattr(owner, "read_exact", None))
                       for key, owner in source_owners.items())
                or context_owners is not None and (
                    not isinstance(context_owners, Mapping)
                    or any(type(key) is not str or not key or owner is None
                           or not callable(getattr(owner, "read_exact", None))
                           for key, owner in context_owners.items()))):
            raise ValueError("AI Task Invocation prepare dependencies required")
        self._uow = unit_of_work
        self._grants = grants
        self._plans = plans
        self._prompts = prompts
        self._sources: dict[str, _ReadOwner] = dict(source_owners)
        self._envelopes = envelopes
        self._contexts: dict[str, _ContextReadOwner] = dict(
            context_owners or {},
        )

    def prepare(self, *, job_id: uuid.UUID, fencing_token: int,
                worker_ref: str, now: datetime) -> PreparedAITaskInvocation:
        if (type(job_id) is not uuid.UUID or not job_id.int
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AITaskInvocationPrepareError()
        now = now.astimezone(timezone.utc)
        try:
            grant = self._grants.issue(
                job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref, now=now,
            )
            query = AIExecutionContentReadQuery(
                grant.content_plan_id, grant.ai_task_id, grant.project_id,
                grant.job_id, grant.requested_by, grant.trace_id,
                grant.authorization_ref, grant.purpose_ref,
                grant.minimal_payload_policy_ref,
            )
            with self._uow() as transaction:
                persisted = self._plans.get(
                    transaction, content_plan_id=grant.content_plan_id,
                )
                if persisted is None:
                    raise AITaskInvocationPrepareError()
                plan = require_content_plan_for_grant(grant, persisted.plan)
                prompt = self._prompts.load_exact(transaction, grant=grant)
                projected: list[AIExecutionContentProjection] = []
                for source in plan.sources:
                    owner = self._sources.get(source.resource_type)
                    if owner is None:
                        raise AITaskInvocationPrepareError()
                    projected.append(owner.read_exact(transaction, query, source))
                exact_sources = tuple(projected)
                context_text = None
                if plan.context.mode == "RAG_CONTEXT":
                    context_owner = self._contexts.get(
                        plan.context.context_policy_ref,
                    )
                    if context_owner is None:
                        raise AITaskInvocationPrepareError()
                    context_text = context_owner.read_exact(
                        transaction, query, plan.context,
                    )
                envelope = self._envelopes.build(
                    plan=plan, sources=exact_sources, prompt_content=prompt,
                    context_text=context_text,
                )
                proof = require_envelope_for_grant(
                    grant, plan, envelope, now=now,
                )
                if (not hmac.compare_digest(
                        persisted.payload_fingerprint,
                        proof.payload_fingerprint)
                        or persisted.record_count != proof.record_count
                        or persisted.payload_bytes != proof.payload_bytes
                        or persisted.input_tokens != proof.input_tokens):
                    raise AITaskInvocationPrepareError()
                prepared = PreparedAITaskInvocation(
                    grant, envelope, proof, _source_node_catalogs(exact_sources),
                )
            self._grants.require_usable(grant)
            return prepared
        except AITaskInvocationPrepareError:
            raise
        except Exception:
            raise AITaskInvocationPrepareError() from None
