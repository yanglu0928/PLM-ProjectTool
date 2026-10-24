"""Pre-SQL invalid sources and exception sanitation, no successful SQL mocks."""
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import Mock, patch

from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_create_result import UserCreateResult
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayError
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.user_repository import AuthTransactionError
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID, PARAMETERS, N, R, P

SOURCE = 'plm_assistant.modules.auth.infrastructure.user_create_result_repository._session'


class UserCreateResultRepositoryDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.verifier = Mock()
        self.repo = SqlAlchemyUserCreateResultRepository(verifier=self.verifier)
        now = datetime.now(timezone.utc)
        self.result = UserCreateResult(UserReadView(uuid4(), 'Synthetic first', 'ENABLED',
            'NONE', 1, now, now, 1), uuid4(), uuid4(), uuid4(), uuid4(), now)

    def assert_fixed_error(self, call):
        with self.assertRaises(UserCreateReplayError) as caught:
            call()
        self.assertEqual(str(caught.exception), 'AUTH_CREATE_REPLAY_UNAVAILABLE')

    def test_all_record_coordinates_refuse_invalid_before_session(self):
        values = {key: uuid4() for key in
                  ('user_id', 'credential_id', 'actor_id', 'audit_event_id', 'trace_id')}
        with patch(SOURCE) as source:
            for key in values:
                for invalid in (None, True, str(uuid4()), UUID(int=0)):
                    with self.subTest(key=key, invalid_type=type(invalid).__name__):
                        self.assert_fixed_error(lambda: self.repo.record(object(), **(values | {key: invalid})))
            source.assert_not_called()
        self.verifier.verify_password.assert_not_called()

    def test_get_invalid_user_refuses_before_session(self):
        with patch(SOURCE) as source:
            for invalid in (None, True, str(uuid4()), UUID(int=0)):
                with self.subTest(invalid_type=type(invalid).__name__):
                    self.assert_fixed_error(lambda: self.repo.get(object(), user_id=invalid))
            source.assert_not_called()
        self.verifier.verify_password.assert_not_called()

    def test_bad_or_tampered_result_refuses_before_session_and_verifier(self):
        with patch(SOURCE) as source:
            for invalid in (None, object(), {'user_id': uuid4()}):
                self.assert_fixed_error(lambda: self.repo.verify_initial_password(object(),
                    result=invalid, password=memoryview(b'Synthetic proof')))
            object.__setattr__(self.result, 'actor_id', None)
            self.assert_fixed_error(lambda: self.repo.verify_initial_password(object(),
                result=self.result, password=memoryview(b'Synthetic proof')))
            source.assert_not_called()
        self.verifier.verify_password.assert_not_called()

    def test_session_fault_in_each_method_has_fixed_error_and_no_verifier(self):
        coordinates = dict(user_id=self.result.first_view.user_id, credential_id=self.result.credential_id,
            actor_id=self.result.actor_id, audit_event_id=self.result.audit_event_id, trace_id=self.result.trace_id)
        calls = (lambda: self.repo.record(object(), **coordinates),
                 lambda: self.repo.get(object(), user_id=self.result.first_view.user_id),
                 lambda: self.repo.verify_initial_password(object(), result=self.result,
                                                           password=memoryview(b'Synthetic proof')))
        for index, call in enumerate(calls):
            for error in (AuthTransactionError, RuntimeError):
                with self.subTest(method=index, failure=error.__name__), patch(
                    SOURCE, side_effect=error('Synthetic private detail')
                ) as source:
                    self.assert_fixed_error(call)
                    source.assert_called_once()
        self.verifier.verify_password.assert_not_called()

    def test_hash_header_salt_profile_and_types_refuse_without_verifier(self):
        valid = f'$scrypt$1${N}${R}${P}$' + '0' * 32 + '$' + '0' * 64
        candidates = ((valid, True, PARAMETERS), (valid, ALGORITHM_ID, None),
            (None, ALGORITHM_ID, PARAMETERS), (valid.replace('$1$', '$2$', 1), ALGORITHM_ID, PARAMETERS),
            (valid.replace('$scrypt$', '$SCRYPT$'), ALGORITHM_ID, PARAMETERS),
            (valid.replace('$' + '0' * 32 + '$', '$z' + '0' * 31 + '$'), ALGORITHM_ID, PARAMETERS))
        for index, arguments in enumerate(candidates):
            with self.subTest(case=index):
                self.assert_fixed_error(lambda: self.repo._validate_hash(*arguments))
        self.verifier.verify_password.assert_not_called()
