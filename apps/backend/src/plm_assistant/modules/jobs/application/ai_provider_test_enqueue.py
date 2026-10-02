"""Trusted AI Provider Test Job/Outbox request; authorization belongs to AI."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.ai.application.probe_policy import PROBE_ID


class AIProviderTestEnqueueError(RuntimeError):
    def __init__(self, code: str = "JOB_STORE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIProviderTestJobRequest:
    submission_id: uuid.UUID
    provider_id: uuid.UUID
    config_id: uuid.UUID
    config_version: int
    secret_version_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    policy_sha256: bytes = field(repr=False)
    probe_id: str = PROBE_ID

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.submission_id, self.provider_id, self.config_id,
                self.secret_version_id, self.actor_id, self.trace_id))
                or type(self.config_version) is not int
                or not 1 <= self.config_version <= 2147483647
                or type(self.policy_sha256) is not bytes or len(self.policy_sha256) != 32
                or self.probe_id != PROBE_ID):
            raise AIProviderTestEnqueueError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AIProviderTestJobRef:
    job_id: uuid.UUID
    event_id: uuid.UUID

    def __post_init__(self) -> None:
        if any(type(value) is not uuid.UUID or not value.int for value in (self.job_id, self.event_id)):
            raise AIProviderTestEnqueueError()


class AIProviderTestQueuePort(Protocol):
    def enqueue(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef: ...
    def find(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef | None: ...


class AIProviderTestJobQueue:
    """Same-UOW queue; the caller must prove authority and commit atomically."""

    def __init__(self, repository: AIProviderTestQueuePort) -> None:
        if repository is None:
            raise ValueError("AI Provider Test queue repository required")
        self._repository = repository

    @staticmethod
    def _request(request: AIProviderTestJobRequest) -> None:
        if type(request) is not AIProviderTestJobRequest:
            raise AIProviderTestEnqueueError("VALIDATION_FAILED")
        request.__post_init__()

    @staticmethod
    def _result(value: AIProviderTestJobRef | None, *, optional: bool = False) -> AIProviderTestJobRef | None:
        if optional and value is None:
            return None
        if type(value) is not AIProviderTestJobRef:
            raise AIProviderTestEnqueueError()
        value.__post_init__()
        return value

    def enqueue(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef:
        self._request(request)
        result = self._result(self._repository.enqueue(transaction, request=request))
        if type(result) is not AIProviderTestJobRef:
            raise AIProviderTestEnqueueError()
        return result

    def find(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef | None:
        self._request(request)
        return self._result(self._repository.find(transaction, request=request), optional=True)
