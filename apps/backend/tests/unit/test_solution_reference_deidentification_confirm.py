from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmationView,
    ReferenceDeidentificationConfirmError, ReferenceDeidentificationConfirmService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceRequest, VerifiedReferenceDocument,
)


NOW = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)
ACTOR, VERSION, DOCUMENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.committed = True


class _Uow:
    def __init__(self):
        self.transactions = []

    def __call__(self):
        tx = _Tx()
        self.transactions.append(tx)
        return tx


class _Access:
    def __init__(self):
        self.actor = ACTOR
        self.calls = []

    def authorized_admin(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.actor


class _License:
    def __init__(self):
        self.failure = None

    def require_valid(self, *, trace_id):
        if self.failure:
            raise self.failure
        return object()


class _Sources:
    def __init__(self):
        self.calls = []
        self.result = ProvenReferenceSources(
            "GLOBAL", None, (VerifiedReferenceDocument(
                DOCUMENT, VERSION, "GLOBAL", None, "REFERENCE_MATERIAL", b"d" * 32),),
            (), b"f" * 32,
        )

    def prove_sources(self, tx, request):
        self.calls.append((tx, request))
        return self.result


class _Repo:
    def __init__(self):
        self.items = {}
        self.calls = []

    def create(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        self.items[kwargs["confirmation_id"]] = ReferenceDeidentificationConfirmationView(
            kwargs["confirmation_id"], kwargs["proven"].content_fingerprint,
            kwargs["actor_id"], kwargs["confirmed_at"], kwargs["expires_at"],
            kwargs["request"].trace_id,
        )

    def view(self, tx, *, confirmation_id, actor_id):
        row = self.items.get(confirmation_id)
        return row if row and row.confirmed_by == actor_id else None


class _Receipts:
    def __init__(self):
        self.records = {}

    def reserve(self, tx, *, scope, request_fingerprint):
        old = self.records.get(scope.key_digest)
        if old is None:
            self.records[scope.key_digest] = (request_fingerprint, None)
            return None
        if old[0] != request_fingerprint:
            raise ValueError("payload conflict")
        return old[1]

    def complete(self, tx, *, scope, result):
        fingerprint, _ = self.records[scope.key_digest]
        self.records[scope.key_digest] = (fingerprint, result)


class _Audit:
    def __init__(self):
        self.calls = []
        self.fail = False

    def append(self, tx, event):
        self.calls.append((tx, event))
        if self.fail:
            raise RuntimeError("audit failed")
        return uuid.uuid4()


class ReferenceDeidentificationConfirmTests(unittest.TestCase):
    def setUp(self):
        self.uow, self.access, self.license = _Uow(), _Access(), _License()
        self.sources, self.repo, self.receipts, self.audit = (
            _Sources(), _Repo(), _Receipts(), _Audit())
        self.service = ReferenceDeidentificationConfirmService(
            unit_of_work=self.uow, access=self.access,
            license_guard=self.license, sources=self.sources,
            repository=self.repo, receipts=self.receipts,
            audit=self.audit, clock=lambda: NOW,
        )
        self.request = ReferenceSourceRequest(
            b"s" * 32, uuid.uuid4(), "GLOBAL", None, (VERSION,), (),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
        )
        self.command = ConfirmReferenceDeidentification(
            self.request, b"c" * 32, NOW + timedelta(days=1),
            "I_VERIFIED_DEIDENTIFICATION", "i" * 16,
        )

    def test_requires_explicit_statement_admin_and_same_transaction_audit(self):
        view = self.service.confirm(self.command)
        self.assertEqual(view.confirmed_by, ACTOR)
        tx = self.uow.transactions[-1]
        self.assertIs(self.sources.calls[0][0], tx)
        self.assertIs(self.repo.calls[0][0], tx)
        self.assertIs(self.audit.calls[0][0], tx)
        self.assertTrue(tx.committed)
        self.assertEqual(self.audit.calls[0][1].action,
                         "SOL_REFERENCE_DEIDENTIFICATION_CONFIRMED")
        self.assertNotIn((b"f" * 32).hex(), repr(view))

    def test_retry_is_one_record_and_one_audit(self):
        first = self.service.confirm(self.command)
        retry = replace(self.command, sources=replace(self.request, trace_id=uuid.uuid4()))
        again = self.service.confirm(retry)
        self.assertEqual(first.confirmation_id, again.confirmation_id)
        self.assertEqual(len(self.repo.calls), 1)
        self.assertEqual(len(self.audit.calls), 1)
        with self.assertRaises(ReferenceDeidentificationConfirmError):
            self.service.confirm(replace(self.command, expires_at=NOW + timedelta(days=2)))

    def test_invalid_statement_scope_expiry_and_csrf_fail_before_sources(self):
        for cmd in (
            replace(self.command, attestation_statement="AI_APPROVED"),
            replace(self.command, sources=replace(self.request, scope="PROJECT")),
            replace(self.command, csrf_token=b"short"),
            replace(self.command, expires_at=NOW),
            replace(self.command, expires_at=NOW + timedelta(days=31)),
        ):
            with self.subTest(cmd=cmd):
                with self.assertRaises(ReferenceDeidentificationConfirmError):
                    self.service.confirm(cmd)
        self.assertEqual(self.sources.calls, [])
        self.assertEqual(self.repo.calls, [])

    def test_denied_admin_license_or_unproven_sources_fail_closed(self):
        self.access.actor = None
        with self.assertRaisesRegex(ReferenceDeidentificationConfirmError, "AUTH_ACCESS_DENIED"):
            self.service.confirm(self.command)
        self.assertEqual(self.sources.calls, [])
        self.access.actor = ACTOR
        self.license.failure = RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        with self.assertRaisesRegex(ReferenceDeidentificationConfirmError, "LICENSE_OPERATION_DENIED"):
            self.service.confirm(self.command)
        self.license.failure = None
        self.sources.result = replace(self.sources.result, scope="PROJECT")
        with self.assertRaises(ReferenceDeidentificationConfirmError):
            self.service.confirm(self.command)
        self.assertEqual(self.repo.calls, [])

    def test_preview_fingerprint_fence_rejects_stale_source_without_writes(self):
        fenced = replace(self.command, expected_source_fingerprint=b"f" * 32)
        self.assertEqual(self.service.confirm(fenced).source_fingerprint, b"f" * 32)
        stale = replace(self.command, idempotency_key="j" * 16,
                        expected_source_fingerprint=b"x" * 32)
        with self.assertRaisesRegex(ReferenceDeidentificationConfirmError,
                                    "SOURCE_SNAPSHOT_CHANGED"):
            self.service.confirm(stale)
        self.assertEqual(len(self.repo.calls), 1)
        self.assertEqual(len(self.audit.calls), 1)
        with self.assertRaisesRegex(ReferenceDeidentificationConfirmError,
                                    "VALIDATION_FAILED"):
            self.service.confirm(replace(self.command,
                expected_source_fingerprint=b"short"))

    def test_audit_failure_does_not_commit(self):
        self.audit.fail = True
        with self.assertRaisesRegex(ReferenceDeidentificationConfirmError, "SOLUTION_UNAVAILABLE"):
            self.service.confirm(self.command)
        self.assertFalse(self.uow.transactions[-1].committed)


if __name__ == "__main__":
    unittest.main()
