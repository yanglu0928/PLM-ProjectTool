"""Reject before obtaining a SQL session; no simulated successful SQL."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from plm_assistant.modules.auth.application.password_change import PasswordChangeError
from plm_assistant.modules.auth.application.password_reset import PasswordResetError
from plm_assistant.modules.auth.application.password_change_actor import PasswordChangeActorProof
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.infrastructure.password_change_repository import SqlAlchemyPasswordChangeRepository
from plm_assistant.modules.auth.infrastructure.password_reset_repository import SqlAlchemyPasswordResetRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID, PARAMETERS


class PasswordRepositoryInputTests(unittest.TestCase):
    def hash_metadata(self):
        return PasswordHashResult('$scrypt$1$131072$8$1$' + '00' * 16 + '$' + '00' * 32,
                                  ALGORITHM_ID, dict(PARAMETERS))

    def proof(self):
        now = datetime.now(timezone.utc)
        view = UserReadView(uuid4(), 'Synthetic adapter user', 'ENABLED', 'NONE', 1, now, now, 1)
        return PasswordChangeActorProof(view, uuid4(), False, uuid4(), 0, now,
                                       now + timedelta(hours=1), now + timedelta(hours=2))

    def test_reset_invalid_inputs_do_not_obtain_session(self):
        valid = dict(user_id=uuid4(), actor_id=uuid4(), expected_version=1, password_hash=self.hash_metadata())
        cases = ({'user_id': UUID(int=0)}, {'user_id': 'client'}, {'actor_id': None},
                 {'expected_version': True}, {'expected_version': -1},
                 {'expected_version': 9223372036854775807}, {'password_hash': object()})
        with patch('plm_assistant.modules.auth.infrastructure.password_reset_repository._session') as session:
            for changes in cases:
                with self.subTest(field=tuple(changes)):
                    with self.assertRaises(PasswordResetError) as caught:
                        SqlAlchemyPasswordResetRepository().reset(object(), **(valid | changes))
                    self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
            session.assert_not_called()

    def test_change_invalid_types_do_not_obtain_session(self):
        with patch('plm_assistant.modules.auth.infrastructure.password_change_repository._session') as session:
            for proof, hashed in ((None, self.hash_metadata()), (object(), self.hash_metadata()), (self.proof(), object())):
                with self.assertRaises(PasswordChangeError):
                    SqlAlchemyPasswordChangeRepository().change(object(), proof=proof, password_hash=hashed)
            session.assert_not_called()

    def test_change_maximum_user_versions_do_not_obtain_session(self):
        with patch('plm_assistant.modules.auth.infrastructure.password_change_repository._session') as session:
            for field in ('credential_version', 'lock_version'):
                proof = self.proof()
                proof = replace(proof, user_view=replace(proof.user_view, **{field: 9223372036854775807}))
                with self.assertRaises(PasswordChangeError):
                    SqlAlchemyPasswordChangeRepository().change(object(), proof=proof, password_hash=self.hash_metadata())
            session.assert_not_called()

    def test_noncanonical_hash_profile_never_obtains_session(self):
        from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayError
        for module, kind in (('password_reset_repository', 'reset'), ('password_change_repository', 'change')):
            with patch('plm_assistant.modules.auth.infrastructure.' + module + '._session') as session:
                for parameters in ({**PARAMETERS, 'p': True}, {**PARAMETERS, 'n': 1}, {}):
                    hashed = PasswordHashResult(self.hash_metadata().password_hash, ALGORITHM_ID, parameters)
                    with self.assertRaises(UserCreateReplayError):
                        if kind == 'reset':
                            SqlAlchemyPasswordResetRepository().reset(object(), user_id=uuid4(), actor_id=uuid4(),
                                                                      expected_version=1, password_hash=hashed)
                        else:
                            SqlAlchemyPasswordChangeRepository().change(object(), proof=self.proof(), password_hash=hashed)
                session.assert_not_called()
