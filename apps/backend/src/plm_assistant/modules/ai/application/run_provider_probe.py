"""Single fixed Provider probe; no persistence, retries or production wiring."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.provider_test_preflight import (
    ProviderTestPreflightError, ProviderTestPreflightService, ProviderTestPreflightSnapshot,
)
from plm_assistant.modules.ai.application.probe_transport_contract import ProbeTransportError
from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError, SecretConsumer, SecretRef, SecretResolver,
)


class ProviderProbeExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProviderProbeObservation:
    job_id: uuid.UUID
    fencing_token: int
    outcome: str = "SUCCEEDED"


class _Connection(Protocol):
    def __enter__(self) -> _Connection: ...
    def __exit__(self, *args: object) -> None: ...
    def send_fixed_probe(self, key: memoryview) -> None: ...


class _Transport(Protocol):
    def open(self, plan: object) -> _Connection: ...


class ProviderProbeRunner:
    def __init__(self, *, preflight: ProviderTestPreflightService,
                 secrets: SecretResolver, transport: _Transport) -> None:
        if any(value is None for value in (preflight, secrets, transport)):
            raise ValueError("Provider probe dependencies required")
        self._preflight, self._secrets, self._transport = preflight, secrets, transport

    def run(self, *, job_id: uuid.UUID, fencing_token: int,
            worker_ref: str, trace_id: uuid.UUID) -> ProviderProbeObservation:
        def check() -> ProviderTestPreflightSnapshot:
            return self._preflight.preflight(
                job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref, trace_id=trace_id,
            )

        try:
            initial = check()
            with self._transport.open(initial.plan) as connection:
                before_send = check()
                if before_send != initial:
                    raise ProviderProbeExecutionError("PROBE_FACTS_CHANGED")
                with self._secrets.use(
                    SecretRef(initial.plan.secret_ref), SecretConsumer.AI_PROVIDER_ADAPTER,
                    expected_version_id=initial.claim.secret_version_id,
                ) as key:
                    connection.send_fixed_probe(key)
            after_send = check()
            if after_send != initial:
                raise ProviderProbeExecutionError("PROBE_FACTS_CHANGED")
            return ProviderProbeObservation(initial.claim.job_id,
                                            initial.claim.fencing_token)
        except ProviderProbeExecutionError:
            raise
        except ProviderTestPreflightError as exc:
            raise ProviderProbeExecutionError(exc.code) from None
        except ProbeTransportError as exc:
            raise ProviderProbeExecutionError(exc.code) from None
        except SecretAccessError:
            raise ProviderProbeExecutionError("PROBE_SECRET_UNAVAILABLE") from None
        except Exception:
            raise ProviderProbeExecutionError("PROBE_UNAVAILABLE") from None
