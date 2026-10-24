from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    LockedRevocationTarget, ReferenceDeidentificationRevokeError,
    ReferenceDeidentificationRevokeService, RevokeReferenceDeidentification,
)


NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
ACTOR = uuid.uuid4()


class _Tx:
    committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
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
    actor = ACTOR

    def authorized_admin(self, tx, **kwargs):
        return self.actor


class _License:
    failure = None

    def require_valid(self, *, trace_id):
        if self.failure:
            raise self.failure
        return object()


class _Repo:
    def __init__(self, ident):
        self.target = LockedRevocationTarget(ident, b"f" * 32, NOW, None)
        self.latest = ident
        self.calls = []

    def lock(self, tx, *, confirmation_id):
        return self.target if confirmation_id == self.target.confirmation_id else None

    def latest_id(self, tx, *, source_fingerprint):
        return self.latest

    def mark_revoked(self, tx, *, confirmation_id, revoked_at):
        self.calls.append((tx, confirmation_id))
        self.target = replace(self.target, revoked_at=revoked_at)
        return True


class _Receipts:
    def __init__(self):
        self.result = None
        self.fingerprint = None

    def reserve(self, tx, *, scope, request_fingerprint):
        if self.fingerprint is not None and self.fingerprint != request_fingerprint:
            raise RuntimeError("conflict")
        self.fingerprint = request_fingerprint
        return self.result

    def complete(self, tx, *, scope, result):
        self.result = result


class _Audit:
    def __init__(self):
        self.calls = []
        self.failure = False

    def append(self, tx, event):
        self.calls.append((tx, event))
        if self.failure:
            raise RuntimeError("audit outage")


class RevocationTests(unittest.TestCase):
    def setUp(self):
        self.ident = uuid.uuid4()
        self.uow, self.access, self.license = _Uow(), _Access(), _License()
        self.repo, self.receipts, self.audit = _Repo(self.ident), _Receipts(), _Audit()
        self.service = ReferenceDeidentificationRevokeService(
            unit_of_work=self.uow, access=self.access, license_guard=self.license,
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: NOW,
        )
        self.command = RevokeReferenceDeidentification(
            self.ident, b"s" * 32, b"c" * 32, uuid.uuid4(), "ADMIN_REVIEW", "i" * 16)

    def test_atomic_revocation_and_replay(self):
        first = self.service.revoke(self.command)
        replay = self.service.revoke(replace(self.command, trace_id=uuid.uuid4()))
        self.assertEqual(first, replay)
        self.assertEqual(len(self.repo.calls), 1)
        self.assertEqual(len(self.audit.calls), 1)
        self.assertIs(self.repo.calls[0][0], self.audit.calls[0][0])
        self.assertEqual(self.audit.calls[0][1].reason_code, "ADMIN_REVIEW")
        self.assertTrue(self.uow.transactions[1].committed)

    def test_validation_admin_license_and_latest_fail_closed(self):
        for cmd in (replace(self.command, reason_code="AI_APPROVED"),
                    replace(self.command, csrf_token=b"bad")):
            with self.assertRaisesRegex(ReferenceDeidentificationRevokeError, "VALIDATION_FAILED"):
                self.service.revoke(cmd)
        self.access.actor = None
        with self.assertRaisesRegex(ReferenceDeidentificationRevokeError, "AUTH_ACCESS_DENIED"):
            self.service.revoke(self.command)
        self.access.actor = ACTOR
        self.license.failure = RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        with self.assertRaisesRegex(ReferenceDeidentificationRevokeError, "LICENSE_OPERATION_DENIED"):
            self.service.revoke(self.command)
        self.license.failure = None
        self.repo.latest = uuid.uuid4()
        with self.assertRaisesRegex(ReferenceDeidentificationRevokeError, "SOLUTION_CONFLICT"):
            self.service.revoke(self.command)
        self.assertFalse(self.repo.calls)

    def test_audit_failure_never_commits(self):
        self.audit.failure = True
        with self.assertRaises(ReferenceDeidentificationRevokeError):
            self.service.revoke(self.command)
        self.assertFalse(self.uow.transactions[-1].committed)


if __name__ == "__main__":
    unittest.main()
