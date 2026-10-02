"""Fail-closed AI Task execution admission over immutable submission evidence."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.create_task import (
    AuthorizedEgressSnapshot, EgressAuthorizationOwnerError, EgressAuthorizationQuery,
)


class AITaskExecutionPreflightError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI_TASK_EXECUTION_NOT_ADMITTED")


@dataclass(frozen=True, slots=True)
class AITaskExecutionSnapshot:
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    task_type: str
    input_fingerprint: bytes = field(repr=False)
    prompt_policy_ref: str
    prompt_policy_version: int
    prompt_template_ref: uuid.UUID
    prompt_version_no: int
    output_schema_ref: str
    context_policy_ref: str
    task_parameters: dict[str, object] = field(repr=False)
    task_parameters_fingerprint: bytes = field(repr=False)
    authorization_ref: uuid.UUID
    authorization_fingerprint: bytes = field(repr=False)
    purpose_ref: str
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    valid_until: datetime


class AITaskExecutionSnapshotRepositoryPort(Protocol):
    def load_for_execution(self, transaction: object, *, ai_task_id: uuid.UUID,
                           project_id: uuid.UUID,
                           job_id: uuid.UUID) -> AITaskExecutionSnapshot | None: ...


class AITaskExecutionEgressOwnerPort(Protocol):
    def resolve_authorized(self, transaction: object, *,
                           query: EgressAuthorizationQuery) -> AuthorizedEgressSnapshot: ...


class AITaskExecutionPreflight:
    """Admit a queued task only if its complete snapshots still resolve live."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: AITaskExecutionSnapshotRepositoryPort,
                 egress_owner: AITaskExecutionEgressOwnerPort) -> None:
        if any(value is None for value in (unit_of_work, repository, egress_owner)):
            raise ValueError("AI Task execution preflight dependencies required")
        self._uow, self._repository, self._egress = unit_of_work, repository, egress_owner

    def require(self, *, ai_task_id: uuid.UUID, project_id: uuid.UUID,
                job_id: uuid.UUID, now: datetime) -> AITaskExecutionSnapshot:
        if (any(type(value) is not uuid.UUID or not value.int
                for value in (ai_task_id, project_id, job_id))
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AITaskExecutionPreflightError()
        now = now.astimezone(timezone.utc)
        try:
            with self._uow() as transaction:
                snapshot = self._repository.load_for_execution(
                    transaction, ai_task_id=ai_task_id,
                    project_id=project_id, job_id=job_id,
                )
                if type(snapshot) is not AITaskExecutionSnapshot:
                    raise AITaskExecutionPreflightError()
                current = self._egress.resolve_authorized(
                    transaction,
                    query=EgressAuthorizationQuery(
                        snapshot.authorization_ref, snapshot.project_id,
                        snapshot.task_type, snapshot.input_fingerprint, now,
                    ),
                )
                if (type(current) is not AuthorizedEgressSnapshot
                        or current.authorization_fingerprint
                        != snapshot.authorization_fingerprint
                        or current.purpose_ref != snapshot.purpose_ref
                        or current.ai_provider_id != snapshot.ai_provider_id
                        or current.provider_config_version_id
                        != snapshot.provider_config_version_id
                        or current.ai_model_id != snapshot.ai_model_id
                        or current.valid_until != snapshot.valid_until
                        or now >= snapshot.valid_until.astimezone(timezone.utc)):
                    raise AITaskExecutionPreflightError()
                return snapshot
        except AITaskExecutionPreflightError:
            raise
        except EgressAuthorizationOwnerError:
            raise AITaskExecutionPreflightError() from None
        except Exception:
            raise AITaskExecutionPreflightError() from None
