import unittest
from uuid import uuid4
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetReplayError


class PasswordResetRepositoryTests(unittest.TestCase):
    def test_requires_actual_verifier(self):
        with self.assertRaises(ValueError):SqlAlchemyPasswordResetResults(verifier=None)

    def test_invalid_id_or_missing_transaction_has_fixed_error(self):
        repo=SqlAlchemyPasswordResetResults(verifier=object())
        for identity in ('client',None,uuid4()):
            with self.assertRaises(PasswordResetReplayError) as caught:repo.get(None,result_id=identity)
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE')

    def test_malformed_draft_password_and_result_fail_closed(self):
        repo=SqlAlchemyPasswordResetResults(verifier=object())
        with self.assertRaises(PasswordResetReplayError):repo.record(None,draft=object())
        with self.assertRaises(PasswordResetReplayError):repo.verify_reset_password(None,result=object(),password=b'client')
