"""Fail-closed Provider Test preflight; explicitly not an egress permit."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbeRegistry, ProbePolicyError, ProviderProbePlan,
    probe_policy_sha256,
)
from plm_assistant.modules.ai.application.submit_provider_test import CurrentProviderTestSource
from plm_assistant.modules.jobs.application.ai_provider_test_claim import (
    AIProviderTestClaim, AIProviderTestClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ProviderTestPreflightError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProviderTestPreflightSnapshot:
    """Ephemeral facts. Must be revalidated by the sending Adapter."""

    claim: AIProviderTestClaim
    plan: ProviderProbePlan = field(repr=False)


class _License(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class _Source(Protocol):
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentProviderTestSource | None: ...


class _Secret(Protocol):
    def active_provider_key_version(self, transaction: object, *, secret_ref: uuid.UUID) -> uuid.UUID | None: ...


class ProviderTestPreflightService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: AIProviderTestClaims, license_guard: _License,
                 source: _Source, secret_proof: _Secret,
                 probe_registry: EndpointProbeRegistry) -> None:
        if any(value is None for value in (
                unit_of_work, claims, license_guard, source, secret_proof, probe_registry)):
            raise ValueError("Provider Test preflight dependencies required")
        self._uow, self._claims, self._guard = unit_of_work, claims, license_guard
        self._source, self._secret, self._registry = source, secret_proof, probe_registry

    def preflight(self, *, job_id: uuid.UUID, fencing_token: int,
                  worker_ref: str, trace_id: uuid.UUID) -> ProviderTestPreflightSnapshot:
        try:
            validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        except JobLeaseError:
            raise ProviderTestPreflightError("JOB_LEASE_LOST") from None
        if type(trace_id) is not uuid.UUID or not trace_id.int:
            raise ProviderTestPreflightError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=trace_id)
            with self._uow() as tx:
                claim = self._claims.check_current(
                    tx, job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
                )
                if claim.trace_id != trace_id:
                    raise ProviderTestPreflightError("JOB_STORE_UNAVAILABLE")
                current = self._source.lock_current(tx, provider_id=claim.provider_id)
                if (type(current) is not CurrentProviderTestSource
                        or current.state not in {"CONFIGURED", "SUSPENDED", "ACTIVE"}
                        or current.config_id != claim.config_id
                        or current.configuration.config_version != claim.config_version
                        or current.configuration.provider_id != claim.provider_id):
                    raise ProviderTestPreflightError("AI_PROVIDER_CONFIG_CHANGED")
                try:
                    plan = self._registry.plan(current.configuration)
                    fingerprint = probe_policy_sha256(current.configuration, plan)
                except ProbePolicyError:
                    raise ProviderTestPreflightError("AI_PROVIDER_POLICY_CHANGED") from None
                if fingerprint != claim.policy_sha256 or plan.probe_id != claim.probe_id:
                    raise ProviderTestPreflightError("AI_PROVIDER_POLICY_CHANGED")
                version = self._secret.active_provider_key_version(
                    tx, secret_ref=plan.secret_ref,
                )
                if version != claim.secret_version_id:
                    raise ProviderTestPreflightError("AI_PROVIDER_SECRET_CHANGED")
            # Guard is checked again after the short database transaction;
            # even this snapshot is not permission to transmit later.
            self._guard.require_valid(trace_id=trace_id)
            return ProviderTestPreflightSnapshot(claim, plan)
        except ProviderTestPreflightError:
            raise
        except RuntimeLicenseError:
            raise ProviderTestPreflightError("LICENSE_OPERATION_DENIED") from None
        except JobLeaseError:
            raise ProviderTestPreflightError("JOB_LEASE_LOST") from None
        except Exception:
            raise ProviderTestPreflightError("AI_PROVIDER_UNAVAILABLE") from None
