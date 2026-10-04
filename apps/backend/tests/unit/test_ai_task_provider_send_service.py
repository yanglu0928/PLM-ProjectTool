from __future__ import annotations

import hashlib
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    AIProviderSendProof,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderPreSendError,
    AuthorizedAIProviderSend,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendError,
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceError,
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
    AITaskPayloadPlanProof,
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    BegunAITaskInvocation,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.application.secret_access import SecretAccessError
from plm_assistant.modules.platform.application.trace_context import current_trace_id
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
)


def _facts():
    now = datetime(2026, 10, 3, 20, tzinfo=timezone.utc)
    project = uuid.uuid4()
    envelope = AIExecutionEnvelope(
        uuid.uuid4(), b"c" * 32, "provider-neutral-json.v1", 1,
        (b"s" * 32,), b'{"messages":[]}', 1, 10,
        "utf8-byte-upper-bound.v1", 1,
    )
    provider, config, model = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    grant = AITaskExecutionGrant(
        uuid.uuid4(), project, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        1, 7, "GAP_ANALYSIS", (AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), project,
        ),), b"i" * 32, "gap-analysis.v1", 1, uuid.uuid4(), 1,
        "a" * 64, "b" * 64, "provider.v1", "gap-output.v1", 1,
        "no-retrieval.v1", b"t" * 32, uuid.uuid4(), uuid.uuid4(),
        b"a" * 32, "project-gap-analysis.v1", provider, config, model,
        "chat-model", "PROVIDER_MANAGED", "cn-beijing",
        ("DOCUMENT_TEXT",), envelope.payload_fingerprint,
        "document-minimal.v1", 1, 65_536, 4_096, 3,
        now + timedelta(minutes=5), envelope.content_plan_id,
    )
    payload = AITaskPayloadPlanProof(
        grant.ai_task_id, grant.job_id, grant.attempt_no,
        execution_grant_fingerprint(grant), grant.source_refs_fingerprint,
        envelope.payload_fingerprint, 1, envelope.payload_bytes,
        envelope.input_tokens,
    )
    prepared = PreparedAITaskInvocation(grant, envelope, payload)
    begun = BegunAITaskInvocation(uuid.uuid4(), grant)
    route = AIProviderExecutionRoute(
        provider, config, model, ProviderKind.OPENAI_COMPATIBLE,
        "endpoint.execution.v1", "https://api.example.test/v1/chat",
        uuid.uuid4(), uuid.uuid4(), "chat-model", "PROVIDER_MANAGED",
        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", 65_536, 3, 5, 20,
    )
    proof = AIProviderSendProof(
        grant.ai_task_id, begun.ai_invocation_id, grant.job_id,
        grant.attempt_no, grant.fencing_token, grant.content_plan_id,
        grant.authorization_ref, execution_grant_fingerprint(grant),
        provider_route_fingerprint(route), envelope.payload_fingerprint,
        envelope.payload_bytes, envelope.input_tokens,
        now + timedelta(minutes=1),
    )
    return now, prepared, begun, AuthorizedAIProviderSend(route, proof)


def _response() -> AIProviderResponse:
    body = bytearray(b'{"choices":[]}')
    return AIProviderResponse(body, AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 10, 2, 5, "STOP",
    ))


class _PreSend:
    def __init__(self, events, values):
        self.events = events
        self.values = list(values)
        self.calls = []

    def authorize(self, **values):
        self.events.append("pre-send")
        self.calls.append(values)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class _AuditScope:
    def __init__(self, events, *, fail=False, fail_exit=False):
        self.events, self.fail, self.fail_exit = events, fail, fail_exit
        self.bound = None

    @contextmanager
    def bind(self, prepared, send):
        if self.fail:
            raise RuntimeError("private audit failure")
        self.bound = (prepared, send)
        self.events.append("audit-enter")
        try:
            yield
        finally:
            self.events.append("audit-exit")
            if self.fail_exit:
                raise RuntimeError("private audit scope exit failure")


class _Secrets:
    def __init__(self, events, trace_id, *, fail=False):
        self.events, self.trace_id, self.fail = events, trace_id, fail
        self.buffer = bytearray(b"synthetic-key")
        self.arguments = None

    @contextmanager
    def use(self, secret_ref, consumer, *, expected_version_id=None):
        self.arguments = (secret_ref, consumer, expected_version_id)
        self.events.append("secret-enter")
        if self.fail:
            self.buffer[:] = b"\x00" * len(self.buffer)
            raise SecretAccessError("secret unavailable")
        self.assert_trace()
        view = memoryview(self.buffer)
        try:
            yield view
        finally:
            view.release()
            self.buffer[:] = b"\x00" * len(self.buffer)
            self.events.append("secret-exit")

    def assert_trace(self):
        if current_trace_id() != self.trace_id:
            raise AssertionError("trace scope missing")


class _Adapter:
    def __init__(self, events, response=None, failure=None):
        self.events, self.response, self.failure = events, response, failure
        self.calls = []

    def send(self, **values):
        self.events.append("adapter")
        self.calls.append(values)
        if self.failure is not None:
            raise self.failure
        return self.response


class _Fence:
    def __init__(self, events, *, fail=False):
        self.events, self.fail = events, fail
        self.calls = []

    def fence(self, **values):
        self.events.append("fence")
        self.calls.append(values)
        if self.fail:
            raise AITaskProviderSendFenceError()


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class _UnitOfWork:
    def __init__(self):
        self.transactions = []

    def __call__(self):
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


class _Claims:
    def __init__(self, claim):
        self.claim = claim
        self.calls = []

    def check_current(self, transaction, **values):
        self.calls.append((transaction, values))
        return self.claim


class _FenceRepository:
    def __init__(self, version=1):
        self.version = version
        self.calls = []

    def mark_running(self, transaction, **values):
        self.calls.append((transaction, values))
        return self.version


class AITaskProviderSendFenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.prepared, self.begun, self.send = _facts()
        grant = self.prepared.grant
        self.claim = AITaskExecutionClaim(
            grant.job_id, grant.ai_task_id, grant.project_id,
            grant.requested_by, grant.trace_id, grant.authorization_ref,
            grant.source_refs_fingerprint, grant.fencing_token,
            grant.attempt_no, grant.max_retry_attempts, self.now,
            self.now + timedelta(minutes=2),
        )

    def service(self, *, claim=None, version=1):
        uow = _UnitOfWork()
        claims = _Claims(claim or self.claim)
        repository = _FenceRepository(version)
        service = AITaskProviderSendFenceService(
            unit_of_work=uow, claims=claims, repository=repository,
        )
        return service, uow, claims, repository

    def fence(self, service, *, send=None):
        return service.fence(
            prepared=self.prepared, begun=self.begun, send=send or self.send,
            job_id=self.prepared.grant.job_id,
            fencing_token=self.prepared.grant.fencing_token,
            worker_ref="worker-a", now=self.now,
        )

    def test_current_claim_commits_exact_running_fence(self):
        service, uow, claims, repository = self.service(version=3)
        result = self.fence(service)
        self.assertEqual(result.ai_invocation_id, self.begun.ai_invocation_id)
        self.assertEqual(result.invocation_lock_version, 3)
        self.assertEqual(result.fenced_at, self.claim.observed_at)
        self.assertTrue(uow.transactions[0].committed)
        self.assertEqual(len(claims.calls), 1)
        self.assertEqual(len(repository.calls), 1)
        self.assertEqual(repository.calls[0][1]["send"], self.send)

    def test_duplicate_or_stale_fence_fails_without_commit(self):
        service, uow, _, repository = self.service(version=None)
        with self.assertRaises(AITaskProviderSendFenceError):
            self.fence(service)
        self.assertFalse(uow.transactions[0].committed)
        self.assertEqual(len(repository.calls), 1)

    def test_identity_or_deadline_drift_fails_closed(self):
        changed = AuthorizedAIProviderSend(
            self.send.route,
            replace(self.send.proof, ai_invocation_id=uuid.uuid4()),
        )
        service, uow, _, repository = self.service()
        with self.assertRaises(AITaskProviderSendFenceError):
            self.fence(service, send=changed)
        self.assertEqual(uow.transactions, [])
        self.assertEqual(repository.calls, [])

        late_claim = replace(
            self.claim,
            observed_at=self.send.proof.valid_until,
            lease_expires_at=self.send.proof.valid_until + timedelta(minutes=1),
        )
        service, uow, _, repository = self.service(claim=late_claim)
        with self.assertRaises(AITaskProviderSendFenceError):
            self.fence(service)
        self.assertFalse(uow.transactions[0].committed)
        self.assertEqual(repository.calls, [])


class AITaskProviderSendServiceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.prepared, self.begun, self.initial = _facts()
        self.events = []

    def service(self, values, *, secret_fail=False, audit_fail=False,
                audit_exit_fail=False,
                fence_fail=False, adapter_failure=None, adapter_response=True):
        pre_send = _PreSend(self.events, values)
        secrets = _Secrets(
            self.events, str(self.prepared.grant.trace_id), fail=secret_fail,
        )
        audit = _AuditScope(
            self.events, fail=audit_fail, fail_exit=audit_exit_fail,
        )
        response = _response() if adapter_response else object()
        adapter = _Adapter(
            self.events, response=response, failure=adapter_failure,
        )
        fence = _Fence(self.events, fail=fence_fail)
        service = AITaskProviderSendService(
            pre_send=pre_send, secrets=secrets, adapter=adapter,
            access_audit_scope=audit, send_fence=fence,
            clock=lambda: self.now,
        )
        return service, pre_send, secrets, audit, fence, adapter, response

    def send(self, service):
        return service.send_once(
            prepared=self.prepared, begun=self.begun,
            job_id=self.prepared.grant.job_id,
            fencing_token=self.prepared.grant.fencing_token,
            worker_ref="worker-a",
        )

    def test_exact_order_allows_only_deadline_refresh_and_returns_owned_response(self):
        refreshed = AuthorizedAIProviderSend(
            self.initial.route,
            replace(
                self.initial.proof,
                valid_until=self.initial.proof.valid_until + timedelta(seconds=5),
            ),
        )
        service, pre_send, secrets, audit, fence, adapter, response = self.service(
            [self.initial, refreshed],
        )
        result = self.send(service)
        self.assertIs(result, response)
        self.assertEqual(self.events, [
            "pre-send", "audit-enter", "secret-enter", "pre-send",
            "fence", "adapter", "secret-exit", "audit-exit",
        ])
        self.assertEqual(len(pre_send.calls), 2)
        self.assertEqual(audit.bound, (self.prepared, self.initial))
        self.assertEqual(
            secrets.arguments[2], self.initial.route.secret_version_id,
        )
        self.assertEqual(adapter.calls[0]["proof"], refreshed.proof)
        self.assertEqual(fence.calls[0]["send"], refreshed)
        self.assertTrue(all(value == 0 for value in secrets.buffer))
        result.close()

    def test_route_or_proof_identity_drift_fails_before_adapter(self):
        changed_route = replace(
            self.initial.route, secret_version_id=uuid.uuid4(),
        )
        cases = (
            AuthorizedAIProviderSend(
                changed_route,
                replace(
                    self.initial.proof,
                    route_fingerprint=provider_route_fingerprint(changed_route),
                ),
            ),
            AuthorizedAIProviderSend(
                self.initial.route,
                replace(self.initial.proof, ai_invocation_id=uuid.uuid4()),
            ),
        )
        for final in cases:
            self.events.clear()
            service, _, secrets, _, _, adapter, response = self.service(
                [self.initial, final],
            )
            with self.subTest(final=final), self.assertRaises(
                    AITaskProviderSendError) as caught:
                self.send(service)
            self.assertEqual(caught.exception.code, "AI_PROVIDER_SEND_FACTS_CHANGED")
            self.assertEqual(adapter.calls, [])
            self.assertTrue(all(value == 0 for value in secrets.buffer))
            response.close()

    def test_second_authorization_or_secret_audit_failure_never_calls_adapter(self):
        cases = (
            ([self.initial, AIProviderPreSendError()], False, False,
             "AI_PROVIDER_SEND_NOT_AUTHORIZED"),
            ([self.initial], True, False, "AI_PROVIDER_SECRET_UNAVAILABLE"),
            ([self.initial], False, True, "AI_PROVIDER_SECRET_UNAVAILABLE"),
        )
        for values, secret_fail, audit_fail, expected in cases:
            self.events.clear()
            service, _, secrets, _, _, adapter, response = self.service(
                values, secret_fail=secret_fail, audit_fail=audit_fail,
            )
            with self.subTest(expected=expected), self.assertRaises(
                    AITaskProviderSendError) as caught:
                self.send(service)
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(adapter.calls, [])
            if not audit_fail:
                self.assertTrue(all(value == 0 for value in secrets.buffer))
            response.close()

        self.events.clear()
        service, _, secrets, _, fence, adapter, response = self.service(
            [self.initial, self.initial], fence_fail=True,
        )
        with self.assertRaises(AITaskProviderSendError) as caught:
            self.send(service)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_SEND_NOT_AUTHORIZED")
        self.assertEqual(len(fence.calls), 1)
        self.assertEqual(adapter.calls, [])
        self.assertTrue(all(value == 0 for value in secrets.buffer))
        response.close()

    def test_adapter_failure_is_safe_and_invalid_response_is_rejected(self):
        service, _, secrets, _, _, _, response = self.service(
            [self.initial, self.initial],
            adapter_failure=AIProviderExecutionError(
                "AI_PROVIDER_NETWORK_UNAVAILABLE",
            ),
        )
        with self.assertRaises(AITaskProviderSendError) as caught:
            self.send(service)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_OUTCOME_UNKNOWN")
        self.assertTrue(caught.exception.provider_outcome_unknown)
        self.assertTrue(all(value == 0 for value in secrets.buffer))
        response.close()

        self.events.clear()
        service, _, secrets, _, _, adapter, _ = self.service(
            [self.initial, self.initial], adapter_response=False,
        )
        with self.assertRaises(AITaskProviderSendError) as caught:
            self.send(service)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_OUTCOME_UNKNOWN")
        self.assertTrue(caught.exception.provider_outcome_unknown)
        self.assertEqual(len(adapter.calls), 1)
        self.assertTrue(all(value == 0 for value in secrets.buffer))

        self.events.clear()
        service, _, secrets, _, _, _, response = self.service(
            [self.initial, self.initial], audit_exit_fail=True,
        )
        with self.assertRaises(AITaskProviderSendError) as caught:
            self.send(service)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_OUTCOME_UNKNOWN")
        self.assertTrue(caught.exception.provider_outcome_unknown)
        with self.assertRaises(AIProviderExecutionError):
            response.view()
        self.assertTrue(all(value == 0 for value in secrets.buffer))


if __name__ == "__main__":
    unittest.main()
