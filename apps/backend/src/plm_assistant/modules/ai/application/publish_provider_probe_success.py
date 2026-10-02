"""Atomic internal publication of one successful fixed Provider probe."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from plm_assistant.modules.ai.application.provider_test_preflight import (
    ProviderTestPreflightError, ProviderTestPreflightService,
)
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeObservation
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


class ProviderProbePublicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _SuccessStore(Protocol):
    def append_success(self, transaction: object, *, snapshot: object) -> uuid.UUID: ...


class _JobFinisher(Protocol):
    def finish(self, transaction: object, *, job_id: uuid.UUID,
               fencing_token: int, worker_ref: str) -> object: ...


class ProviderProbeSuccessPublisher:
    """No network or retries; the caller owns a trusted in-process observation."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 preflight: ProviderTestPreflightService,
                 store: _SuccessStore, jobs: _JobFinisher,
                 audit: ProviderProbeAudit) -> None:
        if any(item is None for item in (unit_of_work, preflight, store, jobs, audit)):
            raise ValueError("Provider probe publication dependencies required")
        self._uow, self._preflight, self._store, self._jobs = (
            unit_of_work, preflight, store, jobs,
        )
        self._audit = audit

    def publish(self, *, observation: ProviderProbeObservation,
                worker_ref: str, trace_id: uuid.UUID) -> uuid.UUID:
        if (type(observation) is not ProviderProbeObservation
                or observation.outcome != "SUCCEEDED"
                or type(trace_id) is not uuid.UUID or not trace_id.int):
            raise ProviderProbePublicationError("VALIDATION_FAILED")
        try:
            validate_checkpoint(job_id=observation.job_id,
                                fencing_token=observation.fencing_token,
                                worker_ref=worker_ref)
            identity = self._audit.capture()
            with self._uow() as tx:
                snapshot = self._preflight.check_locked(
                    tx, job_id=observation.job_id,
                    fencing_token=observation.fencing_token,
                    worker_ref=worker_ref, trace_id=trace_id,
                )
                if (snapshot.claim.job_id != observation.job_id
                        or snapshot.claim.fencing_token != observation.fencing_token):
                    raise ProviderProbePublicationError("JOB_LEASE_LOST")
                result_id = self._store.append_success(tx, snapshot=snapshot)
                finished = self._jobs.finish(
                    tx, job_id=observation.job_id,
                    fencing_token=observation.fencing_token,
                    worker_ref=worker_ref,
                )
                if (finished.job_id != snapshot.claim.job_id
                        or finished.fencing_token != snapshot.claim.fencing_token
                        or finished.attempt_no != snapshot.claim.attempt_no
                        or finished.job_type != "AI_PROVIDER_TEST"):
                    raise ProviderProbePublicationError("JOB_STORE_UNAVAILABLE")
                self._audit.append(tx, claim=snapshot.claim, actor_id=identity,
                                   action="AI_PROVIDER_TEST_SUCCEEDED",
                                   outcome="SUCCESS", state="SUCCEEDED")
                self._audit.assert_same(identity)
                tx.commit()
                return result_id
        except ProviderProbePublicationError:
            raise
        except ProviderTestPreflightError as exc:
            raise ProviderProbePublicationError(exc.code) from None
        except JobLeaseError:
            raise ProviderProbePublicationError("JOB_LEASE_LOST") from None
        except Exception:
            raise ProviderProbePublicationError("AI_PROVIDER_UNAVAILABLE") from None
