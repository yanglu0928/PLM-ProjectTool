"""Session Port refusal/cleanup tests; no simulated successful database SQL."""
import hashlib
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import UUID, uuid4

from plm_assistant.modules.auth.application.session_service import (
    PasswordIssueProof, SessionError, SessionRecord, SessionService,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class SessionServiceDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.uid, self.sid, self.trace = uuid4(), uuid4(), uuid4()
        self.token, self.csrf = b't' * 32, b'c' * 32
        self.record = SessionRecord(self.sid, self.uid, 1, hashlib.sha256(self.csrf).digest(),
            self.now + timedelta(hours=2), self.now + timedelta(hours=1), None, 'ENABLED', 1)
        self.repo, self.audit, self.issue_access, self.admin, self.receipts = (Mock() for _ in range(5))
        self.repo.find_by_token_digest.return_value = self.record
        self.repo.current_credential_version.return_value = 1
        self.issue_access.can_issue.return_value = True
        self.admin.can_revoke_user_sessions.return_value = True
        self.receipts.reserve.return_value = None
        self.transactions, self.closed = [], []

    @contextmanager
    def uow(self):
        tx = Mock()
        self.transactions.append(tx)
        try:
            yield tx
        finally:
            self.closed.append(tx)

    def service(self, **overrides):
        deps = dict(unit_of_work=self.uow, repository=self.repo, issue_access=self.issue_access,
                    audit=self.audit, admin_access=self.admin, idempotency=self.receipts,
                    clock=lambda: self.now)
        return SessionService(**(deps | overrides))

    def no_commit(self):
        self.assertEqual(self.closed, self.transactions)
        for tx in self.transactions:
            tx.commit.assert_not_called()

    def test_required_dependencies_and_missing_proof_refuse_before_transaction(self):
        for field in ('unit_of_work', 'repository', 'issue_access', 'audit'):
            with self.assertRaisesRegex(ValueError, '^session dependencies are required$'):
                self.service(**{field: None})
        with self.assertRaises(SessionError) as caught:
            self.service().issue(user_id=self.uid, trace_id=self.trace, proof=None)
        self.assertEqual(caught.exception.code, 'AUTH_ACCESS_DENIED')
        self.assertEqual(self.transactions, [])
        self.repo.current_credential_version.assert_not_called()

    def test_invalid_ids_tokens_and_clocks_refuse_without_transaction(self):
        for uid in (None, True, 'client', UUID(int=0)):
            proof = PasswordIssueProof(bytearray(b'Synthetic test only'))
            with self.assertRaises(SessionError) as caught:
                self.service().issue(user_id=uid, trace_id=self.trace, proof=proof)
            self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
            self.assertFalse(any(proof.password))
        for now in (None, True, 'clock', datetime(2026, 9, 27)):
            proof = PasswordIssueProof(bytearray(b'Synthetic test only'))
            with self.assertRaises(SessionError) as caught:
                self.service(clock=lambda: now).issue(user_id=self.uid, trace_id=self.trace, proof=proof)
            self.assertEqual(caught.exception.code, 'AUTH_CLOCK_UNAVAILABLE')
            self.assertFalse(any(proof.password))
        for token in (None, bytearray(32), b't' * 31, b't' * 33):
            with self.assertRaises(SessionError) as caught:
                self.service().validate(token)
            self.assertEqual(caught.exception.code, 'AUTH_SESSION_EXPIRED')
        self.assertEqual(self.transactions, [])
        self.repo.find_by_token_digest.assert_not_called()

    def test_revoke_and_renew_refuse_csrf_or_failed_revoke_no_write(self):
        for operation in ('revoke', 'renew'):
            for bad_csrf in (True, False):
                self.setUp()
                self.repo.revoke.return_value = False
                random = Mock(side_effect=(b'n' * 32, b's' * 32))
                with self.assertRaises(SessionError) as caught:
                    getattr(self.service(random_bytes=random), operation)(token=self.token,
                        csrf_token=b'x' * 32 if bad_csrf else self.csrf, trace_id=self.trace)
                self.assertEqual(caught.exception.code, 'AUTH_ACCESS_DENIED' if bad_csrf else 'AUTH_SESSION_EXPIRED')
                if bad_csrf:
                    self.repo.revoke.assert_not_called()
                    random.assert_not_called()
                else:
                    self.repo.revoke.assert_called_once()
                self.repo.create.assert_not_called()
                self.audit.append.assert_not_called()
                self.no_commit()

    def test_logout_missing_dependencies_record_csrf_or_failed_revoke_refuse(self):
        for scenario in ('no_receipts', 'no_record', 'csrf', 'revoke'):
            self.setUp()
            service = self.service(idempotency=None) if scenario == 'no_receipts' else self.service()
            if scenario == 'no_record':
                self.repo.find_by_token_digest.return_value = None
            self.repo.revoke.return_value = False
            with self.assertRaises(SessionError) as caught:
                service.logout(token=self.token, csrf_token=b'x' * 32 if scenario == 'csrf' else self.csrf,
                               trace_id=self.trace, idempotency_key=str(uuid4()))
            expected = {'no_receipts': 'SYSTEM_UNAVAILABLE', 'no_record': 'AUTH_SESSION_EXPIRED',
                        'csrf': 'AUTH_ACCESS_DENIED', 'revoke': 'AUTH_SESSION_EXPIRED'}[scenario]
            self.assertEqual(caught.exception.code, expected)
            if scenario != 'revoke':
                self.receipts.reserve.assert_not_called()
                self.repo.revoke.assert_not_called()
            self.receipts.complete.assert_not_called()
            self.audit.append.assert_not_called()
            self.no_commit()

    def test_logout_replay_current_and_receipt_mismatch_refuse_without_write(self):
        for scenario in ('missing_current', 'not_revoked', 'wrong_reason', 'wrong_ref', 'wrong_status'):
            self.setUp()
            current = replace(self.record, revoked_at=self.now, revoke_reason='LOGOUT')
            receipt = IdempotencyResult('V1_AUTH_SESSION', self.sid, 200)
            if scenario == 'missing_current':
                current = None
            elif scenario == 'not_revoked':
                current = self.record
            elif scenario == 'wrong_reason':
                current = replace(current, revoke_reason='RENEWED')
            elif scenario == 'wrong_ref':
                receipt = replace(receipt, ref_id=uuid4())
            elif scenario == 'wrong_status':
                receipt = replace(receipt, status_code=201)
            self.repo.find_by_token_digest.side_effect = [self.record, current]
            self.receipts.reserve.return_value = receipt
            with self.assertRaises(SessionError) as caught:
                self.service().logout(token=self.token, csrf_token=self.csrf,
                                      trace_id=self.trace, idempotency_key=str(uuid4()))
            self.assertEqual(caught.exception.code, 'SYSTEM_UNAVAILABLE')
            self.repo.revoke.assert_not_called()
            self.receipts.complete.assert_not_called()
            self.audit.append.assert_not_called()
            self.no_commit()

    def test_admin_lock_failure_refuses_before_bulk_revoke(self):
        self.repo.lock_user.return_value = False
        with self.assertRaises(SessionError) as caught:
            self.service().revoke_user_sessions(actor_id=uuid4(), user_id=self.uid, trace_id=self.trace)
        self.assertEqual(caught.exception.code, 'AUTH_ACCESS_DENIED')
        self.repo.revoke_user_sessions.assert_not_called()
        self.audit.append.assert_not_called()
        self.no_commit()
