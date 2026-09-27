"""Access input rejection without any simulated successful SQL."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from sqlalchemy.orm import Session
from plm_assistant.modules.auth.application.session_service import PasswordIssueProof
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.infrastructure.password_change_access import (
    SqlAlchemyPasswordChangeAccess, PasswordChangeAccessError,
)
from plm_assistant.modules.auth.infrastructure.password_reset_access import (
    SqlAlchemyPasswordResetAccess, PasswordResetAccessError,
)
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID, PARAMETERS


class PasswordAccessInputTests(unittest.TestCase):
    def inputs(self):
        return dict(session_token=b't' * 32, csrf_token=b'c' * 32,
                    now=datetime.now(timezone.utc))

    def source(self):
        return PasswordHashResult('$scrypt$1$131072$8$1$' + '00' * 16 + '$' + '00' * 32,
                                  ALGORITHM_ID, dict(PARAMETERS))

    def test_malformed_proof_inputs_never_obtain_session(self):
        cases = ({'session_token': None}, {'session_token': bytearray(32)},
                 {'session_token': b't' * 31}, {'csrf_token': 'c' * 32},
                 {'csrf_token': b'c' * 33}, {'now': True},
                 {'now': datetime(2026, 9, 27)}, {'now': None})
        for cls, helper in (
            (SqlAlchemyPasswordChangeAccess, 'password_change_access._session'),
            (SqlAlchemyPasswordResetAccess, 'user_state_access.SqlAlchemyUserStateAccess.prove'),
        ):
            with patch('plm_assistant.modules.auth.infrastructure.' + helper) as database:
                for changes in cases:
                    with self.subTest(adapter=cls.__name__, field=tuple(changes)):
                        self.assertIsNone(cls(verifier=Mock()).prove(object(), **(self.inputs() | changes)))
                database.assert_not_called()

    def test_transaction_failures_have_fixed_access_errors(self):
        for cls, error, helper, message in (
            (SqlAlchemyPasswordChangeAccess, PasswordChangeAccessError,
             'password_change_access._session', 'AUTH_PASSWORD_ACCESS_UNAVAILABLE'),
            (SqlAlchemyPasswordResetAccess, PasswordResetAccessError,
             'user_state_access.SqlAlchemyUserStateAccess.prove', 'AUTH_PASSWORD_RESET_ACCESS_UNAVAILABLE'),
        ):
            with patch('plm_assistant.modules.auth.infrastructure.' + helper,
                       side_effect=RuntimeError('Synthetic private transaction detail')):
                with self.assertRaises(error) as caught:
                    cls(verifier=Mock()).prove(object(), **self.inputs())
                self.assertEqual(str(caught.exception), message)
                self.assertTrue(caught.exception.__suppress_context__)

    def test_change_invalid_final_or_source_proof_never_obtains_session(self):
        access = SqlAlchemyPasswordChangeAccess(verifier=Mock())
        with patch('plm_assistant.modules.auth.infrastructure.password_change_access._session') as database:
            for proof in (None, object()):
                with self.assertRaises(PasswordChangeAccessError):
                    access.current_password_source(object(), proof=proof)
                self.assertIs(access.require_changed(object(), proof=proof, result=object(),
                                                    trace_id=uuid4(), **self.inputs()), False)
            for changes in ({'csrf_token': b''}, {'now': None}, {'trace_id': None}):
                self.assertIs(access.require_changed(object(), proof=object(), result=object(),
                    **(self.inputs() | {'trace_id': uuid4()} | changes)), False)
            database.assert_not_called()

    def test_invalid_password_source_never_calls_verifier(self):
        verifier = Mock()
        access = SqlAlchemyPasswordChangeAccess(verifier=verifier)
        empty, oversized = memoryview(bytearray()), memoryview(bytearray(1025))
        valid = memoryview(bytearray(b'Synthetic test only'))
        try:
            cases = ((object(), valid), (self.source(), b'wrong type'),
                     (self.source(), empty), (self.source(), oversized),
                     (PasswordHashResult('invalid', ALGORITHM_ID, dict(PARAMETERS)), valid))
            for source, password in cases:
                with self.assertRaises(PasswordChangeAccessError) as caught:
                    access.verify_password_source(source=source, password=password)
                self.assertEqual(str(caught.exception), 'AUTH_PASSWORD_ACCESS_UNAVAILABLE')
            verifier.verify_password.assert_not_called()
        finally:
            for value in (empty, oversized, valid):
                value.release()

    def test_verifier_failure_and_nonboolean_are_fixed_errors(self):
        password = memoryview(bytearray(b'Synthetic test only'))
        try:
            for response in (None, 1, RuntimeError('Synthetic private verifier detail')):
                verifier = Mock()
                if isinstance(response, Exception):
                    verifier.verify_password.side_effect = response
                else:
                    verifier.verify_password.return_value = response
                with self.assertRaises(PasswordChangeAccessError) as caught:
                    SqlAlchemyPasswordChangeAccess(verifier=verifier).verify_password_source(
                        source=self.source(), password=password)
                self.assertEqual(str(caught.exception), 'AUTH_PASSWORD_ACCESS_UNAVAILABLE')
                verifier.verify_password.assert_called_once()
            for matched in (True, False):
                verifier = Mock()
                verifier.verify_password.return_value = matched
                self.assertIs(SqlAlchemyPasswordChangeAccess(verifier=verifier).verify_password_source(
                    source=self.source(), password=password), matched)
        finally:
            password.release()

    def test_issue_invalid_proof_never_reads_transaction(self):
        class UnreadableTransaction:
            @property
            def session(self):
                raise AssertionError('Invalid proof accessed transaction')
        verifier = Mock()
        access = SqlAlchemyPasswordIssueAccess(verifier)
        for proof in (None, object(), PasswordIssueProof('wrong type'),
                      PasswordIssueProof(bytearray()), PasswordIssueProof(bytearray(1025))):
            self.assertIs(access.can_issue(UnreadableTransaction(), uuid4(), 1, proof), False)
        verifier.verify_password.assert_not_called()

    def test_issue_missing_wrong_or_inactive_transaction_fails_closed(self):
        class FailedTransaction:
            @property
            def session(self):
                raise RuntimeError('Synthetic private transaction detail')
        verifier = Mock()
        access = SqlAlchemyPasswordIssueAccess(verifier)
        with Session() as inactive:
            for tx in (object(), FailedTransaction(), SimpleNamespace(session=object()),
                       SimpleNamespace(session=inactive)):
                with self.assertRaises(RuntimeError) as caught:
                    access.can_issue(tx, uuid4(), 1, PasswordIssueProof(bytearray(b'Synthetic only')))
                self.assertEqual(str(caught.exception), 'active auth transaction is required')
        verifier.verify_password.assert_not_called()
