from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.solution.application.prove_reference_deidentification import (
    LockedReferenceDeidentification, ReferenceDeidentificationProofService,
)


NOW = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)
ACTOR = uuid.uuid4()


class _Admins:
    def __init__(self):
        self.actor = ACTOR
        self.calls = []

    def authorized_admin(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.actor


class _Confirmations:
    def __init__(self):
        self.result = LockedReferenceDeidentification(
            uuid.uuid4(), b"f" * 32, "PLM", "DEIDENTIFIED",
            {"industry": "synthetic"}, "I_VERIFIED_DEIDENTIFICATION",
            uuid.uuid4(), NOW - timedelta(hours=1), NOW + timedelta(days=1), None,
        )
        self.calls = []

    def latest(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.result


class ReferenceDeidentificationProofTests(unittest.TestCase):
    def setUp(self):
        self.tx = object()
        self.admins, self.confirmations = _Admins(), _Confirmations()
        self.service = ReferenceDeidentificationProofService(
            admins=self.admins, confirmations=self.confirmations, clock=lambda: NOW)
        self.args = dict(
            session_token=b"s" * 32, trace_id=uuid.uuid4(),
            source_fingerprint=b"f" * 32,
            source_project_class="PLM", deidentification_class="DEIDENTIFIED",
            applicability={"industry": "synthetic"},
        )

    def prove(self, **changes):
        return self.service.prove(self.tx, **(self.args | changes))

    def test_current_admin_and_same_transaction_return_bound_confirmation(self):
        proof = self.prove()
        self.assertEqual(proof.confirmation_id, self.confirmations.result.confirmation_id)
        self.assertEqual(proof.authorized_admin_id, ACTOR)
        self.assertIs(self.admins.calls[0][0], self.tx)
        self.assertIs(self.confirmations.calls[0][0], self.tx)
        self.assertNotIn((b"f" * 32).hex(), repr(proof))

    def test_missing_admin_rejects_before_record_lookup(self):
        self.admins.actor = None
        self.assertIsNone(self.prove())
        self.assertEqual(self.confirmations.calls, [])

    def test_source_metadata_and_statement_drift_fail_closed(self):
        self.assertIsNone(self.prove(source_project_class="OTHER"))
        self.assertIsNone(self.prove(deidentification_class="RAW"))
        self.assertIsNone(self.prove(applicability={"industry": "other"}))
        self.confirmations.result = replace(
            self.confirmations.result, attestation_statement="AI_APPROVED")
        self.assertIsNone(self.prove())

    def test_expired_future_revoked_and_missing_fail_closed(self):
        for proof in (
            None,
            replace(self.confirmations.result, confirmed_at=NOW + timedelta(seconds=1)),
            replace(self.confirmations.result, expires_at=NOW),
            replace(self.confirmations.result, revoked_at=NOW - timedelta(seconds=1)),
        ):
            with self.subTest(proof=proof):
                self.confirmations.result = proof
                self.assertIsNone(self.prove())

    def test_invalid_request_never_looks_up_admin(self):
        self.assertIsNone(self.prove(session_token=b"short"))
        self.assertIsNone(self.prove(source_fingerprint=b"bad"))
        self.assertIsNone(self.prove(trace_id=uuid.UUID(int=0)))
        self.assertEqual(self.admins.calls, [])


if __name__ == "__main__":
    unittest.main()
