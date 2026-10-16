import unittest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_create_result import UserCreateResult
from plm_assistant.modules.auth.application.user_create_replay import (
    UserCreateReplayVerifier,UserCreatePasswordProof,UserCreateReplayError)
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID,PARAMETERS,N,R,P


class UserCreateReplayTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.result=UserCreateResult(UserReadView(uuid4(),'Synthetic user','ENABLED','NONE',1,now,now,1),
            uuid4(),uuid4(),uuid4(),uuid4(),now)
        self.source=Mock();self.source.verify_initial_password.return_value=True
        self.service=UserCreateReplayVerifier(source=self.source)
        self.tx=Mock()

    def test_exact_success_consumes_proof_no_commit(self):
        proof=UserCreatePasswordProof(bytearray(' 密码é '.encode()))
        self.assertNotIn('密码',repr(proof));self.assertNotIn('password=',repr(proof))
        self.assertIs(self.service.require_match(self.tx,result=self.result,proof=proof),self.result)
        self.assertEqual(proof.password,bytearray(len(' 密码é '.encode())))
        self.source.verify_initial_password.assert_called_once()
        self.tx.commit.assert_not_called()

    def test_wrong_password_exact_false_is_conflict_and_erased(self):
        self.source.verify_initial_password.return_value=False
        proof=UserCreatePasswordProof(bytearray(b'Synthetic wrong'))
        with self.assertRaises(UserCreateReplayError) as caught:
            self.service.require_match(self.tx,result=self.result,proof=proof)
        self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY')
        self.assertFalse(any(proof.password));self.tx.commit.assert_not_called()

    def test_fault_or_nonbool_is_unavailable_never_conflict(self):
        for value in (None,1,'yes'):
            self.source.verify_initial_password.return_value=value
            proof=UserCreatePasswordProof(bytearray(b'Synthetic input'))
            with self.assertRaises(UserCreateReplayError) as caught:
                self.service.require_match(self.tx,result=self.result,proof=proof)
            self.assertEqual(str(caught.exception),'AUTH_CREATE_REPLAY_UNAVAILABLE')
            self.assertFalse(any(proof.password))
        self.source.verify_initial_password.side_effect=RuntimeError('private verifier failure')
        proof=UserCreatePasswordProof(bytearray(b'Synthetic input'))
        with self.assertRaises(UserCreateReplayError) as caught:
            self.service.require_match(self.tx,result=self.result,proof=proof)
        self.assertNotIn('private',str(caught.exception));self.assertFalse(any(proof.password))

    def test_invalid_utf8_nul_bounds_types_never_verify(self):
        for value in (bytearray(),bytearray(b'\xff'),bytearray(b'a\x00b'),bytearray(b'x'*1025),b'not mutable',None):
            proof=UserCreatePasswordProof(value)
            with self.assertRaises(UserCreateReplayError) as caught:
                self.service.require_match(self.tx,result=self.result,proof=proof)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED')
            if type(value) is bytearray:self.assertFalse(any(value))
        self.source.verify_initial_password.assert_not_called()

    def test_invalid_or_tampered_result_still_erases(self):
        proof=UserCreatePasswordProof(bytearray(b'Synthetic input'))
        with self.assertRaises(UserCreateReplayError):
            self.service.require_match(self.tx,result=object(),proof=proof)
        self.assertFalse(any(proof.password))
        object.__setattr__(self.result,'actor_id',None)
        proof=UserCreatePasswordProof(bytearray(b'Synthetic input'))
        with self.assertRaises(UserCreateReplayError) as caught:
            self.service.require_match(self.tx,result=self.result,proof=proof)
        self.assertEqual(caught.exception.code,'AUTH_CREATE_REPLAY_UNAVAILABLE')
        self.assertFalse(any(proof.password));self.source.verify_initial_password.assert_not_called()

    def test_static_hash_profile_strict_no_bool_or_foreign_work_cost(self):
        valid=f'$scrypt$1${N}${R}${P}$'+('0'*32)+'$'+('0'*64)
        check=SqlAlchemyUserCreateResultRepository._validate_hash
        check(valid,ALGORITHM_ID,dict(PARAMETERS))
        for encoded,algorithm,parameters in ((valid,'TEST_ONLY',dict(PARAMETERS)),
            (valid,ALGORITHM_ID,PARAMETERS|{'p':True}),(valid,ALGORITHM_ID,PARAMETERS|{'n':N*2}),
            (valid[:-1]+'z',ALGORITHM_ID,dict(PARAMETERS)),(valid[:-1],ALGORITHM_ID,dict(PARAMETERS))):
            with self.assertRaises(UserCreateReplayError):check(encoded,algorithm,parameters)

    def test_repository_requires_transaction_and_missing_dependencies(self):
        with self.assertRaises(ValueError):SqlAlchemyUserCreateResultRepository(verifier=None)
        with self.assertRaises(ValueError):UserCreateReplayVerifier(source=None)
        repo=SqlAlchemyUserCreateResultRepository(verifier=Mock())
        with self.assertRaises(UserCreateReplayError):repo.get(object(),user_id=uuid4())

    def test_unknown_error_code_cannot_expose_private_details(self):
        self.assertEqual(str(UserCreateReplayError('private password detail')),'AUTH_CREATE_REPLAY_UNAVAILABLE')
