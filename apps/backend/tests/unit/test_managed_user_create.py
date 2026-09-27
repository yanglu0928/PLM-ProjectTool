import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock
from plm_assistant.modules.auth.application.managed_user_create import (
    CreateManagedUser,ManagedUserCreateService,ManagedUserCreateError,OPERATION)
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_create_result import UserCreateResult
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayError
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult,canonical_payload_fingerprint
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ManagedUserCreateTests(unittest.TestCase):
    def setUp(self):
        self.tx=Mock();self.uow=Mock();self.uow.return_value.__enter__=Mock(return_value=self.tx)
        self.uow.return_value.__exit__=Mock(return_value=False)
        self.actor=uuid4();self.user=uuid4();self.credential=uuid4();self.event=uuid4();self.trace=uuid4()
        self.access=Mock();self.access.authorized_admin.return_value=self.actor
        self.guard=Mock();self.users=Mock();self.results=Mock();self.receipts=Mock();self.audit=Mock()
        self.replay=Mock();self.hasher=Mock();self.receipts.reserve.return_value=None
        self.users.add_user.return_value=self.user;self.users.add_credential.return_value=self.credential
        self.users.activate_initial_credential.return_value=True;self.audit.append.return_value=self.event
        now=datetime.now(timezone.utc)
        self.result=UserCreateResult(UserReadView(self.user,'Synthetic user','ENABLED','NONE',1,now,now,1),
            self.credential,self.actor,self.event,self.trace,now)
        self.results.record.return_value=self.result;self.results.get.return_value=self.result
        self.replay.require_match.return_value=self.result
        self.hasher.hash_password.return_value=PasswordHashResult('UNIT_ONLY','SCRYPT',{'n':131072})
        self.service=ManagedUserCreateService(unit_of_work=self.uow,access=self.access,license_guard=self.guard,
            users=self.users,results=self.results,replay_verifier=self.replay,hasher=self.hasher,
            audit=self.audit,receipts=self.receipts)
        self.command=CreateManagedUser(b's'*32,b'c'*32,self.trace,' Synthetic user ',bytearray(b'Synthetic password'))
        self.key='Synthetic-key-0001'

    def test_first_atomic_sources_and_nonsecret_fingerprint(self):
        self.assertEqual(self.service.create(self.command,idempotency_key=self.key),self.result.first_view)
        self.tx.commit.assert_called_once();self.assertFalse(any(self.command.password))
        self.assertEqual(self.access.authorized_admin.call_count,2);self.assertEqual(self.guard.require_valid.call_count,2)
        args=self.receipts.reserve.call_args.kwargs
        self.assertEqual(args['scope'].actor_id,self.actor);self.assertIsNone(args['scope'].project_id)
        self.assertEqual(args['request_fingerprint'],canonical_payload_fingerprint({
            'username_display':'Synthetic user','username_normalized':'synthetic user','request_schema':1}))
        self.assertEqual(self.receipts.complete.call_args.kwargs['result'],IdempotencyResult(OPERATION,self.user,201))
        self.replay.require_match.assert_not_called()
        self.assertNotIn('Synthetic password',repr(self.command));self.assertNotIn('session_token=',repr(self.command))

    def test_exact_replay_needs_password_and_current_authority_without_writes(self):
        self.receipts.reserve.return_value=IdempotencyResult(OPERATION,self.user,201)
        self.assertEqual(self.service.create(self.command,idempotency_key=self.key),self.result.first_view)
        self.replay.require_match.assert_called_once();self.tx.commit.assert_not_called()
        self.users.add_user.assert_not_called();self.hasher.hash_password.assert_not_called()
        self.audit.append.assert_not_called();self.results.record.assert_not_called();self.receipts.complete.assert_not_called()
        self.assertFalse(any(self.command.password));self.assertEqual(self.access.authorized_admin.call_count,2)

    def test_wrong_password_replay_conflicts_no_commit(self):
        self.receipts.reserve.return_value=IdempotencyResult(OPERATION,self.user,201)
        self.replay.require_match.side_effect=UserCreateReplayError('CONFLICT_IDEMPOTENCY')
        with self.assertRaises(ManagedUserCreateError) as caught:self.service.create(self.command,idempotency_key=self.key)
        self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY');self.tx.commit.assert_not_called()
        self.assertFalse(any(self.command.password))

    def test_invalid_input_erases_and_does_not_start_transaction(self):
        for change in ({'csrf_token':b'x'}, {'username':''},{'password':bytearray(b'\xff')},
                       {'password':bytearray(b'x\x00y')},{'password':bytearray(b'x'*1025)}):
            cmd=replace(self.command,password=bytearray(b'Synthetic input'),**change) if 'password' not in change else replace(self.command,**change)
            with self.assertRaises(ManagedUserCreateError) as caught:self.service.create(cmd,idempotency_key=self.key)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED');self.assertFalse(any(cmd.password))
        self.uow.assert_not_called();self.guard.require_valid.assert_not_called()

    def test_unknown_current_actor_never_reserves(self):
        self.access.authorized_admin.return_value=None
        with self.assertRaises(ManagedUserCreateError) as caught:self.service.create(self.command,idempotency_key=self.key)
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');self.receipts.reserve.assert_not_called()
        self.tx.commit.assert_not_called();self.assertFalse(any(self.command.password))

    def test_final_license_or_auth_refusal_never_commits(self):
        for kind in ('license','actor'):
            self.setUp()
            if kind=='license':self.guard.require_valid.side_effect=[None,RuntimeLicenseError('EXPIRED')]
            else:self.access.authorized_admin.side_effect=[self.actor,None]
            with self.assertRaises(ManagedUserCreateError):self.service.create(self.command,idempotency_key=self.key)
            self.receipts.complete.assert_called_once();self.tx.commit.assert_not_called()
            self.assertFalse(any(self.command.password))

    def test_username_conflict_fault_or_wrong_snapshot_safe(self):
        for kind in ('duplicate','audit','snapshot','hash','commit'):
            self.setUp()
            if kind=='duplicate':self.users.add_user.return_value=None
            elif kind=='audit':self.audit.append.side_effect=RuntimeError('private SQL')
            elif kind=='snapshot':self.results.record.return_value=replace(self.result,actor_id=uuid4())
            elif kind=='hash':self.hasher.hash_password.return_value=PasswordHashResult('private','TEST_ONLY',{})
            else:self.tx.commit.side_effect=RuntimeError('private commit confirmation')
            with self.assertRaises(ManagedUserCreateError) as caught:self.service.create(self.command,idempotency_key=self.key)
            self.assertEqual(caught.exception.code,'AUTH_USERNAME_CONFLICT' if kind=='duplicate' else 'AUTH_CREATE_UNAVAILABLE')
            self.assertFalse(any(self.command.password))

    def test_replay_wrong_binding_never_password_verifies(self):
        self.receipts.reserve.return_value=IdempotencyResult(OPERATION,self.user,201)
        self.results.get.return_value=replace(self.result,actor_id=uuid4())
        with self.assertRaises(ManagedUserCreateError):self.service.create(self.command,idempotency_key=self.key)
        self.replay.require_match.assert_not_called();self.tx.commit.assert_not_called()

    def _assert_denied_closed_and_erased(self, code='AUTH_CREATE_UNAVAILABLE'):
        with self.assertRaises(ManagedUserCreateError) as caught:
            self.service.create(self.command, idempotency_key=self.key)
        self.assertEqual(caught.exception.code, code)
        self.tx.commit.assert_not_called()
        self.assertFalse(any(self.command.password))
        self.uow.return_value.__exit__.assert_called_once()

    def test_all_required_dependencies_refuse_none(self):
        dependencies = dict(unit_of_work=self.uow, access=self.access, license_guard=self.guard,
            users=self.users, results=self.results, replay_verifier=self.replay, hasher=self.hasher,
            audit=self.audit, receipts=self.receipts)
        for key in dependencies:
            with self.subTest(dependency=key), self.assertRaises(ValueError):
                ManagedUserCreateService(**(dependencies | {key: None}))
        self.uow.assert_not_called()

    def test_malformed_receipts_refuse_before_result_or_hash(self):
        for kind in ('type', 'operation', 'status'):
            self.setUp()
            receipt = (object() if kind == 'type' else IdempotencyResult(
                'V1_OTHER_CREATE' if kind == 'operation' else OPERATION, self.user,
                200 if kind == 'status' else 201))
            self.receipts.reserve.return_value = receipt
            with self.subTest(kind=kind):
                self._assert_denied_closed_and_erased()
                self.results.get.assert_not_called()
                self.replay.require_match.assert_not_called()
                self.users.add_user.assert_not_called()
                self.hasher.hash_password.assert_not_called()
                self.receipts.complete.assert_not_called()

    def test_replay_result_identity_and_proof_return_refuse_no_write(self):
        for kind in ('missing', 'display', 'receipt_user', 'proof_result'):
            self.setUp()
            self.receipts.reserve.return_value = IdempotencyResult(
                OPERATION, uuid4() if kind == 'receipt_user' else self.user, 201)
            if kind == 'missing':
                self.results.get.return_value = None
            elif kind == 'display':
                self.results.get.return_value = replace(self.result,
                    first_view=replace(self.result.first_view, username_display='Synthetic mismatch'))
            elif kind == 'proof_result':
                self.replay.require_match.return_value = None
            with self.subTest(kind=kind):
                self._assert_denied_closed_and_erased()
                self.assertEqual(self.replay.require_match.call_count, int(kind == 'proof_result'))
                self.hasher.hash_password.assert_not_called()
                self.users.add_user.assert_not_called()
                self.audit.append.assert_not_called()
                self.receipts.complete.assert_not_called()

    def test_write_source_identity_activation_and_first_coordinates_refuse(self):
        for kind in ('user', 'credential', 'activation', 'audit', 'first_user',
                     'first_credential', 'first_audit', 'first_trace'):
            self.setUp()
            if kind == 'user':
                self.users.add_user.return_value = True
            elif kind == 'credential':
                self.users.add_credential.return_value = True
            elif kind == 'activation':
                self.users.activate_initial_credential.return_value = 1
            elif kind == 'audit':
                self.audit.append.return_value = True
            elif kind == 'first_user':
                self.results.record.return_value = replace(self.result,
                    first_view=replace(self.result.first_view, user_id=uuid4()))
            else:
                field = {'first_credential': 'credential_id', 'first_audit': 'audit_event_id',
                         'first_trace': 'trace_id'}[kind]
                self.results.record.return_value = replace(self.result, **{field: uuid4()})
            with self.subTest(kind=kind):
                self._assert_denied_closed_and_erased()
                self.receipts.complete.assert_not_called()
                if kind in ('user', 'credential', 'activation'):
                    self.audit.append.assert_not_called()

    def test_invalid_clock_refuses_before_receipt_and_hash(self):
        for value in (None, True, 'Synthetic time', datetime.now()):
            self.setUp()
            self.service._clock = Mock(return_value=value)
            with self.subTest(clock_type=type(value).__name__):
                self._assert_denied_closed_and_erased()
                self.access.authorized_admin.assert_not_called()
                self.receipts.reserve.assert_not_called()
                self.hasher.hash_password.assert_not_called()

    def test_hash_contract_wrong_types_keys_and_costs_refuse_before_user(self):
        candidates = (None, PasswordHashResult('', 'SCRYPT', {'n': 1}),
            PasswordHashResult('x', True, {'n': 1}),
            PasswordHashResult('x', 'SCRYPT', None), PasswordHashResult('x', 'SCRYPT', {}),
            PasswordHashResult('x', 'SCRYPT', {str(i): 1 for i in range(17)}),
            PasswordHashResult('x', 'SCRYPT', {1: 1}),
            PasswordHashResult('x', 'SCRYPT', {'非ASCII': 1}),
            PasswordHashResult('x', 'SCRYPT', {'bad-key': 1}),
            PasswordHashResult('x', 'SCRYPT', {'n': True}),
            PasswordHashResult('x', 'SCRYPT', {'n': -1}),
            PasswordHashResult('x', 'SCRYPT', {'n': 1_000_000_001}))
        for index, candidate in enumerate(candidates):
            self.setUp()
            self.hasher.hash_password.return_value = candidate
            with self.subTest(case=index):
                self._assert_denied_closed_and_erased()
                self.users.add_user.assert_not_called()
                self.audit.append.assert_not_called()
                self.receipts.complete.assert_not_called()
