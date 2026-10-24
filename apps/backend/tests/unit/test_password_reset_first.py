import unittest
from dataclasses import replace,FrozenInstanceError
from datetime import datetime,timezone,timedelta
from uuid import uuid4,UUID
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.password_reset_replay import (
    PasswordResetProof,PasswordResetReplayVerifier,PasswordResetReplayError)
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher


def first():
    now=datetime.now(timezone.utc)
    return PasswordResetResult(uuid4(),uuid4(),uuid4(),uuid4(),uuid4(),1,2,1,2,'ENABLED',uuid4(),uuid4(),0,now,now)


class ResetFirstTests(unittest.TestCase):
    def test_normal_disabled_and_self_all_have_only_version_public(self):
        result=first()
        for state in ('ENABLED','DISABLED'):
            for self_reset in (False,True):
                value=replace(result,target_state=state,actor_id=result.user_id if self_reset else result.actor_id)
                self.assertEqual(value.public_data(),{'credential_version':2})
                with self.assertRaises(FrozenInstanceError):value.credential_version=3

    def test_strict_ids_versions_counts_state_and_time(self):
        result=first()
        for field,value in (('result_id',UUID(int=0)),('actor_id','client'),('credential_id',result.before_credential_id),
            ('credential_version',True),('before_credential_version',0),('credential_version',3),
            ('user_version',3),('before_user_version',-1),('revoked_session_count',True),
            ('revoked_session_count',-1),('revoked_session_count',9223372036854775808),('target_state','OTHER'),
            ('changed_at',datetime.now()),('accepted_at',result.changed_at-timedelta(seconds=1))):
            with self.subTest(field=field,value=str(value)):
                with self.assertRaisesRegex(ValueError,'AUTH_PASSWORD_RESET_RESULT_UNAVAILABLE'):replace(result,**{field:value})

    def test_input_bounds_utf8_and_finally_erasure(self):
        class Source:
            calls=0
            def verify_reset_password(self,*args,**kwargs):self.calls+=1;return True
        source=Source();verifier=PasswordResetReplayVerifier(source=source)
        for secret in (bytearray(),bytearray(b'x'*1025),bytearray(b'\x00'),bytearray(b'\xff')):
            proof=PasswordResetProof(secret)
            with self.assertRaises(PasswordResetReplayError) as caught:verifier.require_match(None,result=first(),proof=proof)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED');self.assertFalse(any(secret))
        self.assertEqual(source.calls,0)
        proof=PasswordResetProof(bytearray(b'x'*1024));result=first()
        self.assertEqual(verifier.require_match(None,result=result,proof=proof),result)
        self.assertFalse(any(proof.temporary_password))

    def test_false_conflict_nonbool_and_exception_static_error(self):
        for value in (False,1,None,RuntimeError('Synthetic private temporary password')):
            class Source:
                def verify_reset_password(self,*args,**kwargs):
                    if isinstance(value,Exception):raise value
                    return value
            proof=PasswordResetProof(bytearray(b'Synthetic private temporary password'))
            with self.assertRaises(PasswordResetReplayError) as caught:
                PasswordResetReplayVerifier(source=Source()).require_match(None,result=first(),proof=proof)
            self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY' if value is False else 'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE')
            self.assertNotIn('private',str(caught.exception));self.assertFalse(any(proof.temporary_password))

    def test_malformed_result_erases_and_password_not_repr(self):
        proof=PasswordResetProof(bytearray(b'Synthetic private password'))
        self.assertNotIn('private',repr(proof))
        with self.assertRaises(PasswordResetReplayError):
            PasswordResetReplayVerifier(source=object()).require_match(None,result=object(),proof=proof)
        self.assertFalse(any(proof.temporary_password))

    def test_real_scrypt_bound_first_not_later_current_password(self):
        result=first();hasher=ScryptPasswordHasher();temporary='Synthetic 临时密码'.encode()
        with memoryview(temporary) as password:original_hash=hasher.hash_password(password)
        with memoryview(b'Synthetic later password') as password:later_hash=hasher.hash_password(password)
        class InMemorySource:
            # Explicit unit fixture, NOT persistent reset repository or current Admin authentication.
            active=later_hash
            def verify_reset_password(self,tx,*,result:PasswordResetResult,password):
                if result!=stored_first:raise RuntimeError('Synthetic forged first')
                return hasher.verify_password(password,password_hash=original_hash.password_hash,
                    algorithm_id=original_hash.algorithm_id,parameter_set=dict(original_hash.parameter_set))
        stored_first=result;source=InMemorySource();verifier=PasswordResetReplayVerifier(source=source)
        def match(secret,expected=None,record=result):
            proof=PasswordResetProof(bytearray(secret))
            try:
                if expected:
                    with self.assertRaises(PasswordResetReplayError) as caught:verifier.require_match(None,result=record,proof=proof)
                    self.assertEqual(caught.exception.code,expected)
                else:self.assertEqual(verifier.require_match(None,result=record,proof=proof),result)
            finally:self.assertFalse(any(proof.temporary_password))
        match(temporary)
        match(temporary+b' ','CONFLICT_IDEMPOTENCY')
        match(b'Synthetic later password','CONFLICT_IDEMPOTENCY')
        match(temporary,'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE',replace(result,credential_id=uuid4()))
