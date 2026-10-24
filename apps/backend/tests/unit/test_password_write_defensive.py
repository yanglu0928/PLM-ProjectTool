"""Service Port failures with explicit commit spies; not actual SQL evidence."""
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import UUID, uuid4

from plm_assistant.modules.auth.application.password_change import ChangePassword, PasswordChangeService, PasswordChangeError
from plm_assistant.modules.auth.application.password_change_actor import PasswordChangeActorProof
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof
from plm_assistant.modules.auth.application.password_reset import ResetPassword, PasswordResetService, PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state import UserStateActorProof


class PasswordWriteDefensiveTests(unittest.TestCase):
    def fixture(self, kind):
        now = datetime.now(timezone.utc); uid = uuid4(); oldid = uuid4(); newid = uuid4()
        before = UserReadView(uid, 'Synthetic writer', 'ENABLED', 'DEPLOYMENT_ADMIN', 1, now, now, 1)
        after = replace(before, credential_version=2, lock_version=2, updated_at=now + timedelta(seconds=1))
        if kind == 'reset':
            proof = UserStateActorProof(before, oldid, uuid4(), 0, now, now + timedelta(hours=1), now + timedelta(hours=2))
            command = ResetPassword(b't' * 32, b'c' * 32, uuid4(), uid, 1, True, PasswordResetProof(bytearray(b'Synthetic temporary')))
        else:
            proof = PasswordChangeActorProof(before, oldid, False, uuid4(), 0, now, now + timedelta(hours=1), now + timedelta(hours=2))
            command = ChangePassword(b't' * 32, b'c' * 32, uuid4(), PasswordChangeProof(bytearray(b'Synthetic old'), bytearray(b'Synthetic new')))
        transactions = []; active = []
        @contextmanager
        def uow():
            tx = Mock(); transactions.append(tx); active.append(tx)
            try: yield tx
            finally: active.remove(tx)
        access = Mock(); access.prove.return_value = proof; access.lock_deployment.return_value = True
        access.current_password_source.return_value = PasswordHashResult('Synthetic source', 'SCRYPT', {})
        access.verify_password_source.return_value = True
        access.require_changed.return_value = True; access.require_self_reset.return_value = True
        repo = Mock()
        repo.reset.return_value = (after, oldid, before, 1, newid)
        repo.change.return_value = (newid, now + timedelta(seconds=1), 1)
        results = Mock(); results.record.side_effect = lambda tx, *, draft: draft
        receipts = Mock(); receipts.lookup_completed.return_value = None; receipts.reserve.return_value = None
        hasher = Mock(); hasher.hash_password.return_value = PasswordHashResult('Synthetic new hash', 'SCRYPT', {})
        audit = Mock(); audit.append.return_value = uuid4()
        deps = dict(unit_of_work=uow, access=access, repository=repo, results=results,
                    replay_verifier=Mock(), hasher=hasher, audit=audit, receipts=receipts)
        if kind == 'reset': deps['license_guard'] = Mock()
        service = (PasswordResetService if kind == 'reset' else PasswordChangeService)(**deps)
        return dict(kind=kind, command=command, service=service, access=access, repo=repo, results=results,
                    receipts=receipts, transactions=transactions, active=active, before=before, after=after,
                    oldid=oldid, newid=newid, now=now, proof=proof)

    def execute(self, f):
        method = f['service'].reset if f['kind'] == 'reset' else f['service'].change
        return method(f['command'], idempotency_key=str(uuid4()))

    def erased(self, f):
        secret = f['command'].password if f['kind'] == 'reset' else f['command'].passwords
        buffers = (secret.temporary_password,) if f['kind'] == 'reset' else (secret.current_password, secret.new_password)
        self.assertTrue(all(not any(value) for value in buffers))
        self.assertEqual(f['active'], [])

    def rejected(self, f):
        with self.assertRaises(PasswordResetError if f['kind'] == 'reset' else PasswordChangeError):
            self.execute(f)
        self.assertEqual(len(f['transactions']), 2)
        for tx in f['transactions']: tx.commit.assert_not_called()
        self.erased(f)

    def test_positive_controls_reach_complete_final_proof_and_one_commit(self):
        for kind in ('reset', 'change'):
            f = self.fixture(kind); result = self.execute(f)
            self.assertEqual(result.credential_version, 2)
            self.assertEqual(len(f['transactions']), 2)
            f['transactions'][0].commit.assert_not_called()
            f['transactions'][1].commit.assert_called_once()
            f['receipts'].complete.assert_called_once()
            final = f['access'].require_self_reset if kind == 'reset' else f['access'].require_changed
            final.assert_called_once(); self.erased(f)

    def test_change_repo_invalid_id_time_count_never_commits(self):
        for fault in ('zero-id', 'bad-time', 'bool-count', 'zero-count'):
            with self.subTest(fault=fault):
                f = self.fixture('change'); uid, at, count = f['repo'].change.return_value
                if fault == 'zero-id': uid = UUID(int=0)
                elif fault == 'bad-time': at = None
                elif fault == 'bool-count': count = True
                else: count = 0
                f['repo'].change.return_value = (uid, at, count)
                self.rejected(f); f['results'].record.assert_not_called(); f['receipts'].complete.assert_not_called()

    def test_reset_repo_view_coordinates_and_count_never_commit(self):
        for fault in ('view-type', 'before-type', 'target', 'before-version', 'new-version', 'same-credential', 'negative-count', 'bool-count'):
            with self.subTest(fault=fault):
                f = self.fixture('reset'); view, oldid, before, count, newid = f['repo'].reset.return_value
                if fault == 'view-type': view = object()
                elif fault == 'before-type': before = object()
                elif fault == 'target': view = replace(view, user_id=uuid4())
                elif fault == 'before-version': before = replace(before, lock_version=0)
                elif fault == 'new-version': view = replace(view, credential_version=3)
                elif fault == 'same-credential': newid = oldid
                elif fault == 'negative-count': count = -1
                else: count = True
                f['repo'].reset.return_value = (view, oldid, before, count, newid)
                self.rejected(f); f['results'].record.assert_not_called(); f['receipts'].complete.assert_not_called()

    def test_unknown_and_mismatched_first_result_never_commits(self):
        for kind in ('reset', 'change'):
            for fault in ('type', 'different-trace'):
                with self.subTest(kind=kind, fault=fault):
                    f = self.fixture(kind)
                    f['results'].record.side_effect = (lambda tx, *, draft: object()) if fault == 'type' else \
                                                       (lambda tx, *, draft: replace(draft, trace_id=uuid4()))
                    self.rejected(f); f['receipts'].complete.assert_not_called()

    def test_false_truthy_or_unknown_final_proof_never_commits(self):
        for kind in ('reset', 'change'):
            for outcome in (False, 1, RuntimeError('Synthetic private final fault')):
                with self.subTest(kind=kind, outcome=type(outcome).__name__):
                    f = self.fixture(kind)
                    final = f['access'].require_self_reset if kind == 'reset' else f['access'].require_changed
                    if isinstance(outcome, Exception): final.side_effect = outcome
                    else: final.return_value = outcome
                    self.rejected(f); f['receipts'].complete.assert_called_once()
