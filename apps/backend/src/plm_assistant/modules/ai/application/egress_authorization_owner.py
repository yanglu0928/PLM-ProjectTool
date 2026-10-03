"""Current Egress Authorization Owner projection for AI Task creation."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Protocol

from plm_assistant.modules.ai.application.create_task import (
    AuthorizedEgressSnapshot, EgressAuthorizationOwnerError, EgressAuthorizationQuery,
)
from plm_assistant.modules.ai.application.egress_authorization import EgressAuthorizationView
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint


_ROLES = {
    "ProjectManager": "PROJECT_MANAGER",
    "CustomerManager": "CUSTOMER_MANAGER",
}


class AITaskEgressPurposeRegistry:
    """Trusted task-to-purpose mapping supplied by deployment composition."""

    def __init__(self, purposes: Mapping[str, frozenset[str]]) -> None:
        if (not isinstance(purposes, Mapping) or not purposes
                or any(type(task_type) is not str or not task_type
                       or type(allowed) is not frozenset or not allowed
                       or any(type(item) is not str or not item for item in allowed)
                       for task_type, allowed in purposes.items())):
            raise ValueError("AI Task egress purpose policy required")
        self._purposes = MappingProxyType(dict(purposes))

    def permits(self, *, task_type: str, purpose_ref: str) -> bool:
        return purpose_ref in self._purposes.get(task_type, frozenset())


class EgressAuthorizationCurrentRepositoryPort(Protocol):
    def resolve_current(self, transaction: object, *, authorization_ref,
                        project_id) -> EgressAuthorizationView | None: ...


def authorization_fingerprint(value: EgressAuthorizationView) -> bytes:
    if type(value) is not EgressAuthorizationView:
        raise EgressAuthorizationOwnerError()
    return canonical_payload_fingerprint({
        "authorization_id": str(value.authorization_id),
        "preview_id": str(value.preview_id), "project_id": str(value.project_id),
        "purpose_ref": value.purpose_ref, "operation_type": value.operation_type,
        "provider_id": str(value.provider_id),
        "provider_config_version_id": str(value.provider_config_version_id),
        "model_id": str(value.model_id), "data_region": value.data_region,
        "allowed_data_categories": list(value.allowed_data_categories),
        "minimal_payload_policy_ref": value.minimal_payload_policy_ref,
        "max_record_count": value.max_record_count,
        "max_payload_bytes": value.max_payload_bytes,
        "max_input_tokens": value.max_input_tokens,
        "max_retry_attempts": value.max_retry_attempts,
        "payload_fingerprint": value.payload_fingerprint.hex(),
        "source_refs_fingerprint": value.source_refs_fingerprint.hex(),
        "approved_by": str(value.approved_by), "approved_role": value.approved_role,
        "approved_at": value.approved_at.isoformat(),
        "valid_until": value.valid_until.isoformat(),
        "state": value.state, "lock_version": value.lock_version,
        "content_plan_ref": (str(value.content_plan_ref)
                             if value.content_plan_ref is not None else None),
    })


class EgressAuthorizationOwner:
    def __init__(self, *, repository: EgressAuthorizationCurrentRepositoryPort,
                 purposes: AITaskEgressPurposeRegistry) -> None:
        if repository is None or purposes is None:
            raise ValueError("Egress Authorization Owner dependencies required")
        self._repository, self._purposes = repository, purposes

    def resolve_authorized(self, transaction: object, *,
                           query: EgressAuthorizationQuery) -> AuthorizedEgressSnapshot:
        if (type(query) is not EgressAuthorizationQuery
                or type(query.authorization_ref) is not uuid.UUID
                or not query.authorization_ref.int
                or type(query.project_id) is not uuid.UUID or not query.project_id.int
                or type(query.task_type) is not str or not query.task_type
                or type(query.source_refs_fingerprint) is not bytes
                or len(query.source_refs_fingerprint) != 32
                or not isinstance(query.now, datetime)
                or query.now.tzinfo is None or query.now.utcoffset() is None):
            raise EgressAuthorizationOwnerError()
        current = self._repository.resolve_current(
            transaction, authorization_ref=query.authorization_ref,
            project_id=query.project_id,
        )
        role = None if current is None else _ROLES.get(current.approved_role)
        if (type(current) is not EgressAuthorizationView
                or current.authorization_id != query.authorization_ref
                or current.project_id != query.project_id
                or current.operation_type != "AI_TASK"
                or type(current.content_plan_ref) is not uuid.UUID
                or not current.content_plan_ref.int
                or current.state != "AUTHORIZED" or current.lock_version != 0
                or current.source_refs_fingerprint != query.source_refs_fingerprint
                or current.approved_at > query.now
                or query.now >= current.valid_until
                or role is None
                or not self._purposes.permits(
                    task_type=query.task_type, purpose_ref=current.purpose_ref,
                )):
            raise EgressAuthorizationOwnerError()
        return AuthorizedEgressSnapshot(
            current.authorization_id, current.project_id, current.purpose_ref,
            current.provider_id, current.provider_config_version_id,
            current.model_id, current.data_region, current.allowed_data_categories,
            authorization_fingerprint(current), current.payload_fingerprint,
            current.source_refs_fingerprint, current.approved_by, role,
            current.approved_at, current.valid_until,
            current.minimal_payload_policy_ref, current.max_record_count,
            current.max_payload_bytes,
            current.max_input_tokens, current.max_retry_attempts, current.state,
            current.content_plan_ref,
        )
