from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    AIProviderSendProof,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AuthorizedAIProviderSend,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
    AITaskPayloadPlanProof,
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
    AITaskSecretAuditError,
)
from plm_assistant.modules.platform.application.secret_access import SecretRef


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


def _facts():
    now = datetime(2026, 10, 3, 18, tzinfo=timezone.utc)
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
    route = AIProviderExecutionRoute(
        provider, config, model, ProviderKind.OPENAI_COMPATIBLE,
        "endpoint.execution.v1", "https://api.example.test/v1/chat",
        uuid.uuid4(), uuid.uuid4(), "chat-model", "PROVIDER_MANAGED",
        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", 65_536, 3, 5, 20,
    )
    proof = AIProviderSendProof(
        grant.ai_task_id, uuid.uuid4(), grant.job_id, grant.attempt_no,
        grant.fencing_token, grant.content_plan_id, grant.authorization_ref,
        execution_grant_fingerprint(grant), provider_route_fingerprint(route),
        envelope.payload_fingerprint, envelope.payload_bytes,
        envelope.input_tokens, now + timedelta(minutes=1),
    )
    return prepared, AuthorizedAIProviderSend(route, proof)


class AITaskProviderSecretAuditTests(unittest.TestCase):
    def setUp(self):
        self.prepared, self.send = _facts()
        self.transaction = _Transaction()
        self.audit = Mock()
        self.audit.append.return_value = uuid.uuid4()
        self.system_id = uuid.uuid4()
        self.actor = Mock(spec=["assert_current"])
        self.actor.assert_current.return_value = self.system_id
        self.service = AITaskProviderSecretAccessAudit(
            unit_of_work=lambda: self.transaction,
            audit=self.audit, system_actor=self.actor,
        )

    def record(self, **changes):
        fields = dict(
            secret_ref=SecretRef(self.send.route.secret_ref),
            consumer="AI_PROVIDER_ADAPTER", outcome="GRANTED",
            trace_id=str(self.prepared.grant.trace_id),
        )
        fields.update(changes)
        self.service.record_access(**fields)

    def test_granted_and_denied_persist_project_task_identity(self):
        with self.service.bind(self.prepared, self.send):
            self.record()
            self.record(outcome="DENIED")
        self.assertTrue(self.transaction.committed)
        events = [call.args[1] for call in self.audit.append.call_args_list]
        self.assertEqual([value.outcome for value in events], ["SUCCESS", "DENIED"])
        for event in events:
            self.assertEqual(event.event_scope, "PROJECT")
            self.assertEqual(event.target_project_id, self.prepared.grant.project_id)
            self.assertEqual(
                (event.actor_type, event.actor_id, event.original_actor_id),
                ("SYSTEM", self.system_id, self.prepared.grant.requested_by),
            )
            self.assertEqual(
                (event.target_object_id, event.target_version_id, event.trace_id),
                (self.send.route.secret_ref, self.send.route.secret_version_id,
                 self.prepared.grant.trace_id),
            )

    def test_missing_nested_or_mismatched_scope_fails_closed(self):
        with self.assertRaises(AITaskSecretAuditError):
            self.record()
        with self.service.bind(self.prepared, self.send):
            for changes in (
                {"secret_ref": SecretRef(uuid.uuid4())},
                {"consumer": "RERANKER_ADAPTER"},
                {"trace_id": str(uuid.uuid4())},
                {"outcome": "UNKNOWN"},
            ):
                with self.subTest(changes=changes), self.assertRaises(
                        AITaskSecretAuditError):
                    self.record(**changes)
            with self.assertRaises(AITaskSecretAuditError):
                with self.service.bind(self.prepared, self.send):
                    pass
        self.audit.append.assert_not_called()

    def test_proof_or_audit_failure_does_not_grant(self):
        for changes in (
            {"grant_fingerprint": b"z" * 32},
            {"payload_fingerprint": b"y" * 32},
            {"payload_bytes": self.send.proof.payload_bytes + 1},
            {"input_tokens": self.send.proof.input_tokens + 1},
        ):
            drifted = AuthorizedAIProviderSend(
                self.send.route, replace(self.send.proof, **changes),
            )
            with self.subTest(changes=changes), self.assertRaises(
                    AITaskSecretAuditError):
                with self.service.bind(self.prepared, drifted):
                    pass
        self.audit.append.side_effect = RuntimeError("private")
        with self.service.bind(self.prepared, self.send):
            with self.assertRaises(AITaskSecretAuditError) as caught:
                self.record()
        self.assertNotIn("private", str(caught.exception))
        self.assertFalse(self.transaction.committed)


if __name__ == "__main__":
    unittest.main()
