"""Pre-SQL name provenance validation; no successful SQL result mocks."""
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import patch

from sqlalchemy.orm import Session
from plm_assistant.modules.auth.domain.username import CanonicalUsername, UsernameValidationError, normalize_username
from plm_assistant.modules.auth.application.user_name_patch import UserNamePatchError
from plm_assistant.modules.auth.infrastructure.user_name_patch_repository import SqlAlchemyUserNamePatchRepository
from plm_assistant.modules.auth.infrastructure.user_repository import AuthTransactionError

SOURCE = 'plm_assistant.modules.auth.infrastructure.user_name_patch_repository._session'


class UserNamePatchRepositoryDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.repo = SqlAlchemyUserNamePatchRepository()
        self.values = dict(user_id=uuid4(), actor_id=uuid4(), expected_version=1,
                           username=normalize_username('Synthetic user'))

    def test_invalid_identity_and_version_refuse_before_session(self):
        with patch(SOURCE) as source:
            for field in ('user_id', 'actor_id', 'expected_version'):
                candidates = ((None, True, '1', -1, 2**63, 1.0) if field == 'expected_version'
                              else (None, True, str(uuid4()), UUID(int=0)))
                for bad in candidates:
                    with self.subTest(field=field, value_type=type(bad).__name__), self.assertRaises(UserNamePatchError) as caught:
                        self.repo.patch(object(), **(self.values | {field: bad}))
                    self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
            source.assert_not_called()

    def test_name_type_and_canonical_provenance_refuse_before_session(self):
        candidates = (None, object(), 'Synthetic user', CanonicalUsername(' Synthetic user ', 'synthetic user'),
                      CanonicalUsername('Synthetic user', 'wrong-source'))
        with patch(SOURCE) as source:
            for index, bad in enumerate(candidates):
                with self.subTest(case=index), self.assertRaises(UserNamePatchError) as caught:
                    self.repo.patch(object(), **(self.values | {'username': bad}))
                self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
            with self.assertRaises(UsernameValidationError):
                self.repo.patch(object(), **(self.values | {'username': CanonicalUsername('', '')}))
            source.assert_not_called()

    def test_genuine_inactive_session_and_wrong_source_never_start_transaction(self):
        with Session() as session:
            for value in (None, object(), session):
                with self.subTest(source_type=type(value).__name__), self.assertRaises(AuthTransactionError):
                    self.repo.patch(SimpleNamespace(session=value), **self.values)
                self.assertFalse(session.in_transaction())

    def test_session_failure_propagates_without_fake_sql_success(self):
        for failure in (AuthTransactionError, RuntimeError):
            with self.subTest(failure=failure.__name__), patch(
                SOURCE, side_effect=failure('Synthetic private transaction')
            ) as source:
                with self.assertRaises(failure):
                    self.repo.patch(object(), **self.values)
                source.assert_called_once()
