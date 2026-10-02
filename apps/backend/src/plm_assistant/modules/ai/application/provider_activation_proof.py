"""Current Provider activation eligibility; caller must still authorize and commit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbeRegistry, ProbePolicyError, probe_policy_sha256,
)
from plm_assistant.modules.ai.application.submit_provider_test import CurrentProviderTestSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ProviderActivationProofError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LatestProviderProbe:
    provider_id: uuid.UUID
    config_id: uuid.UUID
    secret_version_id: uuid.UUID
    job_id: uuid.UUID
    result_id: uuid.UUID
    policy_sha256: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.provider_id, self.config_id, self.secret_version_id,
                self.job_id, self.result_id))
                or type(self.policy_sha256) is not bytes or len(self.policy_sha256) != 32):
            raise ProviderActivationProofError()


@dataclass(frozen=True, slots=True)
class ProviderActivationProof:
    provider_id: uuid.UUID
    config_id: uuid.UUID
    secret_version_id: uuid.UUID
    result_id: uuid.UUID
    job_id: uuid.UUID
    lock_version: int


class _Current(Protocol):
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentProviderTestSource | None: ...


class _Secret(Protocol):
    def active_provider_key_version(self, transaction: object, *, secret_ref: uuid.UUID) -> uuid.UUID | None: ...


class _Latest(Protocol):
    def latest_success(self, transaction: object, *, provider_id: uuid.UUID) -> LatestProviderProbe | None: ...


class ProviderActivationProofService:
    """No authorization, state write or egress; invoke inside activation UOW."""

    def __init__(self, *, current: _Current, secrets: _Secret,
                 policies: EndpointProbeRegistry, latest: _Latest,
                 license_guard: object) -> None:
        if any(value is None for value in (current, secrets, policies, latest, license_guard)):
            raise ValueError("Current Provider activation proof dependencies required")
        self._current, self._secrets, self._policies = current, secrets, policies
        self._latest, self._guard = latest, license_guard

    def require_locked(self, transaction: object, *, provider_id: uuid.UUID,
                       trace_id: uuid.UUID) -> ProviderActivationProof:
        if (type(provider_id) is not uuid.UUID or not provider_id.int
                or type(trace_id) is not uuid.UUID or not trace_id.int):
            raise ProviderActivationProofError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=trace_id)
            current = self._current.lock_current(transaction, provider_id=provider_id)
            if current is None:
                raise ProviderActivationProofError("AI_PROVIDER_NOT_FOUND")
            if (type(current) is not CurrentProviderTestSource
                    or current.configuration.provider_id != provider_id
                    or current.state not in {"CONFIGURED", "SUSPENDED", "ACTIVE"}):
                raise ProviderActivationProofError("AI_PROVIDER_STATE_CONFLICT")
            try:
                plan = self._policies.plan(current.configuration)
                digest = probe_policy_sha256(current.configuration, plan)
            except ProbePolicyError:
                raise ProviderActivationProofError("AI_PROVIDER_POLICY_UNAVAILABLE") from None
            version = self._secrets.active_provider_key_version(
                transaction, secret_ref=plan.secret_ref,
            )
            if type(version) is not uuid.UUID or not version.int:
                raise ProviderActivationProofError("AI_PROVIDER_SECRET_UNAVAILABLE")
            latest = self._latest.latest_success(transaction, provider_id=provider_id)
            if (type(latest) is not LatestProviderProbe
                    or latest.provider_id != provider_id
                    or latest.config_id != current.config_id
                    or latest.secret_version_id != version
                    or latest.policy_sha256 != digest):
                raise ProviderActivationProofError("AI_PROVIDER_TEST_REQUIRED")
            latest.__post_init__()
            self._guard.require_valid(trace_id=trace_id)
            return ProviderActivationProof(provider_id, current.config_id, version,
                                           latest.result_id, latest.job_id,
                                           current.lock_version)
        except ProviderActivationProofError:
            raise
        except RuntimeLicenseError:
            raise ProviderActivationProofError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ProviderActivationProofError() from None
