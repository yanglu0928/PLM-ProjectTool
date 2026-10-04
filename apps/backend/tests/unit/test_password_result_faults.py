"""Immutable result adapters fail closed before/at an unavailable transaction."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetReplayError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeReplayError
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults
from plm_assistant.modules.auth.infrastructure.scrypt_password import PARAMETERS


class PasswordResultFaultTests(unittest.TestCase):
    def cases(self):
        now = datetime.now(timezone.utc)
        reset = PasswordResetResult(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(),
                                    1, 2, 1, 2, 'ENABLED', uuid4(), uuid4(), 1, now, now)
        change = PasswordChangeResult(uuid4(), uuid4(), uuid4(), uuid4(),
                                      1, 2, 1, 2, uuid4(), uuid4(), 1, now, now)
        yield SqlAlchemyPasswordResetResults, PasswordResetReplayError, reset, {}, 'password_reset_result_repository'
        yield SqlAlchemyPasswordChangeResults, PasswordChangeReplayError, change, {'role': 'BEFORE'}, 'password_change_result_repository'
        yield SqlAlchemyPasswordChangeResults, PasswordChangeReplayError, change, {'role': 'AFTER'}, 'password_change_result_repository'

    def source(self):
        return PasswordHashResult('$scrypt$1$131072$8$1$' + 'a' * 32 + '$' + 'b' * 64,
                                  'SCRYPT', dict(PARAMETERS))

    def test_transaction_failure_get_record_source_and_recheck_fixed(self):
        for cls, error, result, role, module in self.cases():
            verifier = Mock()
            repo = cls(verifier=verifier)
            with patch('plm_assistant.modules.auth.infrastructure.' + module + '._session',
                       side_effect=RuntimeError('Synthetic private driver detail')) as session:
                calls = (lambda: repo.get(object(), result_id=result.result_id),
                         lambda: repo.record(object(), draft=result),
                         lambda: repo.password_source(object(), result=result, **role),
                         lambda: repo.require_password_source(object(), result=result, source=self.source(), **role))
                for index, call in enumerate(calls):
                    with self.subTest(adapter=cls.__name__, role=role, operation=index):
                        with self.assertRaises(error) as caught:
                            call()
                        expected = ('AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE' if not role
                                    else 'AUTH_PASSWORD_REPLAY_UNAVAILABLE')
                        self.assertEqual(str(caught.exception), expected)
                        self.assertTrue(caught.exception.__suppress_context__)
                self.assertEqual(session.call_count, 4)
                verifier.verify_password.assert_not_called()

    def test_change_invalid_role_never_obtains_session(self):
        _, _, result, _, _ = list(self.cases())[1]
        repo = SqlAlchemyPasswordChangeResults(verifier=Mock())
        with patch('plm_assistant.modules.auth.infrastructure.password_change_result_repository._session') as session:
            for role in (None, True, b'BEFORE', 'before', 'OTHER', ''):
                with self.assertRaises(PasswordChangeReplayError):
                    repo.password_source(object(), result=result, role=role)
                with self.assertRaises(PasswordChangeReplayError):
                    repo.require_password_source(object(), result=result, role=role, source=self.source())
            session.assert_not_called()

    def test_invalid_result_and_recheck_source_do_not_obtain_session(self):
        for cls, error, result, role, module in self.cases():
            verifier = Mock()
            repo = cls(verifier=verifier)
            with patch('plm_assistant.modules.auth.infrastructure.' + module + '._session') as session:
                for malformed in (None, object()):
                    with self.assertRaises(error):
                        repo.password_source(object(), result=malformed, **role)
                    with self.assertRaises(error):
                        repo.record(object(), draft=malformed)
                    with self.assertRaises(error):
                        repo.require_password_source(object(), result=result, source=malformed, **role)
                session.assert_not_called()
                verifier.verify_password.assert_not_called()
