from __future__ import annotations

import unittest
import uuid
from unittest.mock import Mock

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.ai.infrastructure.provider_probe_secret_audit import (
    ProviderProbeSecretAccessAudit, ProviderProbeSecretAuditError,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.platform.application.secret_access import SecretRef


class Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def commit(self):
        self.committed = True


class ProviderProbeSecretAuditTests(unittest.TestCase):
    def setUp(self):
        self.secret_id = uuid.uuid4()
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), b"p" * 32, 1, 1,
        )
        self.snapshot = ProviderTestPreflightSnapshot(
            self.claim,
            ProviderProbePlan(self.claim.provider_id, 1, "policy.test",
                              "https://probe.example.test/v1/chat", "synthetic-chat",
                              self.secret_id),
        )
        self.transaction = Transaction()
        self.audit = Mock()
        self.audit.append.return_value = uuid.uuid4()
        self.actor_id = uuid.uuid4()
        self.actor = Mock(spec=["assert_current"])
        self.actor.assert_current.return_value = self.actor_id
        self.service = ProviderProbeSecretAccessAudit(
            unit_of_work=lambda: self.transaction, audit=self.audit,
            system_actor=self.actor,
        )

    def record(self, **changes):
        fields = dict(secret_ref=SecretRef(self.secret_id),
                      consumer="AI_PROVIDER_ADAPTER", outcome="GRANTED",
                      trace_id=str(self.claim.trace_id))
        fields.update(changes)
        self.service.record_access(**fields)

    def test_granted_and_denied_persist_actor_and_version(self):
        with self.service.bind(self.snapshot):
            self.record()
            self.record(outcome="DENIED")
        self.assertTrue(self.transaction.committed)
        events = [call.args[1] for call in self.audit.append.call_args_list]
        self.assertEqual([event.outcome for event in events], ["SUCCESS", "DENIED"])
        for event in events:
            self.assertEqual((event.actor_type, event.actor_id, event.original_actor_id),
                             ("SYSTEM", self.actor_id, self.claim.actor_id))
            self.assertEqual((event.target_object_id, event.target_version_id,
                              event.trace_id),
                             (self.secret_id, self.claim.secret_version_id,
                              self.claim.trace_id))

    def test_missing_scope_and_mismatch_fail_closed(self):
        with self.assertRaises(ProviderProbeSecretAuditError):
            self.record()
        with self.service.bind(self.snapshot):
            for changes in (
                dict(secret_ref=SecretRef(uuid.uuid4())),
                dict(consumer="RERANKER_ADAPTER"),
                dict(trace_id=str(uuid.uuid4())),
                dict(outcome="UNKNOWN"),
            ):
                with self.subTest(changes=changes), self.assertRaises(ProviderProbeSecretAuditError):
                    self.record(**changes)
            with self.assertRaises(ProviderProbeSecretAuditError):
                with self.service.bind(self.snapshot):
                    pass
        self.assertFalse(self.transaction.committed)
        self.audit.append.assert_not_called()

    def test_audit_or_actor_failure_does_not_grant(self):
        for failing in ("actor", "audit"):
            with self.subTest(failing=failing):
                self.actor.assert_current.return_value = self.actor_id
                self.audit.append.side_effect = None
                if failing == "actor":
                    self.actor.assert_current.side_effect = RuntimeError("private")
                else:
                    self.actor.assert_current.side_effect = None
                    self.audit.append.side_effect = RuntimeError("private")
                with self.service.bind(self.snapshot):
                    with self.assertRaises(ProviderProbeSecretAuditError) as caught:
                        self.record()
                self.assertNotIn("private", str(caught.exception))
                self.assertFalse(self.transaction.committed)


if __name__ == "__main__":
    unittest.main()
