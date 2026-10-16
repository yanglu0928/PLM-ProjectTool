import unittest
from uuid import uuid4
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeReplayError


class PasswordChangeRepositoryTests(unittest.TestCase):
    def setUp(self):self.repo=SqlAlchemyPasswordChangeResults(verifier=object())

    def test_requires_verifier(self):
        with self.assertRaises(ValueError):SqlAlchemyPasswordChangeResults(verifier=None)

    def test_bad_input_static_unavailable(self):
        for call in (lambda:self.repo.get(None,result_id='client'),lambda:self.repo.get(None,result_id=uuid4()),
            lambda:self.repo.record(None,draft=object()),
            lambda:self.repo.verify_credential_password(None,result=object(),role='BEFORE',password=memoryview(b'x'))):
            with self.assertRaises(PasswordChangeReplayError) as caught:call()
            self.assertEqual(caught.exception.code,'AUTH_PASSWORD_REPLAY_UNAVAILABLE')
