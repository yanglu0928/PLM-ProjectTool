"""Pre-SQL source refusal, with genuine inactive SQLAlchemy Sessions."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import patch

from sqlalchemy.orm import Session
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state import ChangeUserState, UserStateActorProof, UserStateError
from plm_assistant.modules.auth.application.user_state_result import UserStateResult
from plm_assistant.modules.auth.infrastructure.user_state_access import SqlAlchemyUserStateAccess
from plm_assistant.modules.auth.infrastructure.user_state_repository import SqlAlchemyUserStateRepository
from plm_assistant.modules.auth.infrastructure.user_repository import AuthTransactionError


class UserStateAdaptersDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.now, self.uid = datetime.now(timezone.utc), uuid4()
        view = UserReadView(self.uid, 'Synthetic Admin', 'ENABLED', 'DEPLOYMENT_ADMIN',
                            1, self.now, self.now, 1)
        self.proof = UserStateActorProof(view, uuid4(), uuid4(), 0, self.now - timedelta(minutes=1),
                                         self.now + timedelta(minutes=30), self.now + timedelta(hours=8))
        self.command = ChangeUserState(b't' * 32, b'c' * 32, uuid4(), self.uid, 1)
        self.result = UserStateResult(uuid4(), replace(view, account_state='DISABLED', lock_version=2),
            self.uid, uuid4(), self.command.trace_id, 'DISABLE', 1, 1, self.now)
        self.access, self.repo = SqlAlchemyUserStateAccess(), SqlAlchemyUserStateRepository()

    def test_repository_invalid_ids_refuse_before_session(self):
        with patch('plm_assistant.modules.auth.infrastructure.user_state_repository._session') as source:
            for field in ('user_id', 'actor_id'):
                for bad in (None, True, str(uuid4()), UUID(int=0)):
                    values = dict(user_id=self.uid, actor_id=self.uid, expected_version=1, operation='DISABLE')
                    with self.subTest(field=field, value_type=type(bad).__name__), self.assertRaises(UserStateError) as caught:
                        self.repo.change(object(), **(values | {field: bad}))
                    self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
            source.assert_not_called()

    def test_self_disable_wrong_source_refuses_before_session(self):
        for kind in ('operation', 'proof_user', 'actor', 'count', 'command_version',
                     'result_version', 'trace', 'target'):
            self.setUp()
            proof, command, result = self.proof, self.command, self.result
            if kind == 'operation':
                result = replace(result, operation='ENABLE', revoked_session_count=0,
                                 first_view=replace(result.first_view, account_state='ENABLED'))
            elif kind == 'proof_user':
                proof = replace(proof, user_view=replace(proof.user_view, user_id=uuid4()))
            elif kind == 'actor': result = replace(result, actor_id=uuid4())
            elif kind == 'count': result = replace(result, revoked_session_count=0)
            elif kind == 'command_version': command = replace(command, expected_version=2)
            elif kind == 'result_version':
                result = replace(result, expected_version=2, first_view=replace(result.first_view, lock_version=3))
            elif kind == 'trace': result = replace(result, trace_id=uuid4())
            else: result = replace(result, first_view=replace(result.first_view, user_id=uuid4()))
            with self.subTest(kind=kind), patch(
                'plm_assistant.modules.auth.infrastructure.user_state_access._session'
            ) as source:
                self.assertIs(self.access.require_self_disabled(object(), proof=proof,
                    command=command, result=result, now=self.now), False)
                source.assert_not_called()

    def test_tampered_proof_or_result_refuse_before_session(self):
        for kind in ('proof', 'result'):
            self.setUp()
            if kind == 'proof': object.__setattr__(self.proof, 'session_version', True)
            else: object.__setattr__(self.result, 'revoked_session_count', True)
            with self.subTest(kind=kind), patch(
                'plm_assistant.modules.auth.infrastructure.user_state_access._session'
            ) as source:
                with self.assertRaises((UserStateError, ValueError)):
                    self.access.require_self_disabled(object(), proof=self.proof,
                        command=self.command, result=self.result, now=self.now)
                source.assert_not_called()

    def test_actual_inactive_session_refuses_lock_change_and_final(self):
        with Session() as session:
            transaction = SimpleNamespace(session=session)
            calls = (lambda: self.access.lock_deployment(transaction),
                     lambda: self.repo.change(transaction, user_id=self.uid, actor_id=self.uid,
                                             expected_version=1, operation='DISABLE'),
                     lambda: self.access.require_self_disabled(transaction, proof=self.proof,
                         command=self.command, result=self.result, now=self.now))
            for index, call in enumerate(calls):
                with self.subTest(method=index), self.assertRaises(AuthTransactionError):
                    call()
                self.assertFalse(session.in_transaction())
