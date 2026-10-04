import unittest
from dataclasses import replace, FrozenInstanceError
from datetime import datetime,timezone,timedelta
from uuid import uuid4, UUID
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_change_replay import (
    PasswordChangeProof,PasswordChangeReplayVerifier,PasswordChangeReplayError)


def result():
    now=datetime.now(timezone.utc)
    return PasswordChangeResult(uuid4(),uuid4(),uuid4(),uuid4(),1,2,0,1,uuid4(),uuid4(),1,now,now)


class Source:
    def __init__(self, returns=(True,True)):
        self.returns=iter(returns);self.calls=[];self.views=[]
    def verify_credential_password(self, tx, *, result, role, password):
        self.calls.append((tx,result,role,bytes(password)));self.views.append(password)
        value=next(self.returns)
        if isinstance(value,Exception):raise value
        return value


class PasswordChangeResultTests(unittest.TestCase):
    def test_private_immutable_and_public_minimum(self):
        first=result();self.assertEqual(first.public_data(),{'credential_version':2})
        with self.assertRaises(FrozenInstanceError):first.credential_version=3

    def test_uuid_coordinates_strict(self):
        first=result()
        for field in ('result_id','user_id','before_credential_id','credential_id','audit_event_id','trace_id'):
            for bad in (UUID(int=0),str(uuid4()),None):
                with self.assertRaises(ValueError):replace(first,**{field:bad})
        with self.assertRaises(ValueError):replace(first,credential_id=first.before_credential_id)

    def test_version_count_and_time_strict(self):
        first=result()
        for field,bad in (('before_credential_version',0),('before_credential_version',True),
            ('credential_version',3),('user_version',0),('before_user_version',-1),
            ('revoked_session_count',0),('revoked_session_count',True),('revoked_session_count',2**63),
            ('accepted_at',first.changed_at-timedelta(seconds=1)),('changed_at',datetime.now())):
            with self.assertRaises(ValueError):replace(first,**{field:bad})
        top=9223372036854775807
        self.assertEqual(replace(first,before_credential_version=top-1,credential_version=top,
            before_user_version=top-1,user_version=top).credential_version,top)

    def test_two_password_matches_release_views_erase_buffers(self):
        first=result();source=Source();proof=PasswordChangeProof(bytearray(b'Synthetic old'),bytearray(b'Synthetic new'))
        self.assertNotIn('Synthetic',repr(proof))
        self.assertIs(PasswordChangeReplayVerifier(source=source).require_match('owned tx',result=first,proof=proof),first)
        self.assertEqual([v[2:] for v in source.calls],[('BEFORE',b'Synthetic old'),('AFTER',b'Synthetic new')])
        self.assertEqual(proof.current_password,bytearray(len(b'Synthetic old')))
        self.assertEqual(proof.new_password,bytearray(len(b'Synthetic new')))
        for view in source.views:
            with self.assertRaises(ValueError):bytes(view)

    def test_either_password_mismatch_conflicts(self):
        for returns in ((False,True),(True,False)):
            proof=PasswordChangeProof(bytearray(b'old'),bytearray(b'new'))
            with self.assertRaises(PasswordChangeReplayError) as caught:
                PasswordChangeReplayVerifier(source=Source(returns)).require_match(None,result=result(),proof=proof)
            self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY')
            self.assertEqual(proof.current_password,bytearray(3));self.assertEqual(proof.new_password,bytearray(3))

    def test_non_bool_and_source_exception_unavailable(self):
        for value in (1,None,'true',RuntimeError('private source')):
            proof=PasswordChangeProof(bytearray(b'old'),bytearray(b'new'))
            with self.assertRaises(PasswordChangeReplayError) as caught:
                PasswordChangeReplayVerifier(source=Source((True,value))).require_match(None,result=result(),proof=proof)
            self.assertEqual(caught.exception.code,'AUTH_PASSWORD_REPLAY_UNAVAILABLE')
            self.assertNotIn('private',str(caught.exception))
            self.assertEqual(proof.new_password,bytearray(3))

    def test_invalid_buffers_no_source_erase_valid_peer(self):
        for secret in (bytearray(),bytearray(b'a\x00b'),bytearray(b'\xff'),bytearray(1025),b'immutable'):
            proof=PasswordChangeProof(secret,bytearray(b'peer'));source=Source()
            with self.assertRaises(PasswordChangeReplayError) as caught:
                PasswordChangeReplayVerifier(source=source).require_match(None,result=result(),proof=proof)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED');self.assertEqual(source.calls,[])
            self.assertEqual(proof.new_password,bytearray(4))

    def test_bad_result_no_source_still_erases(self):
        proof=PasswordChangeProof(bytearray(b'old'),bytearray(b'new'));source=Source()
        with self.assertRaises(PasswordChangeReplayError):PasswordChangeReplayVerifier(source=source).require_match(None,result=object(),proof=proof)
        self.assertEqual(source.calls,[]);self.assertEqual(proof.current_password,bytearray(3))

    def test_actual_scrypt_two_independent_credentials(self):
        from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
        hasher=ScryptPasswordHasher();first=result()
        old='Synthetic 原密码'.encode('utf-8');new='Synthetic 新密码'.encode('utf-8')
        hashes={}
        for role,raw in (('BEFORE',old),('AFTER',new)):
            with memoryview(raw) as view:hashes[role]=hasher.hash_password(view)
        class ActualKdfSource:
            def verify_credential_password(self,tx,*,result,role,password):
                if result is not first:raise RuntimeError('Unbound test source')
                stored=hashes[role]
                return hasher.verify_password(password,password_hash=stored.password_hash,
                    algorithm_id=stored.algorithm_id,parameter_set=stored.parameter_set)
        verifier=PasswordChangeReplayVerifier(source=ActualKdfSource())
        proof=PasswordChangeProof(bytearray(old),bytearray(new))
        self.assertIs(verifier.require_match(None,result=first,proof=proof),first)
        for before,after in ((new,new),(old,old),(old,new+b' ')):
            proof=PasswordChangeProof(bytearray(before),bytearray(after))
            with self.assertRaises(PasswordChangeReplayError) as caught:
                verifier.require_match(None,result=first,proof=proof)
            self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY')
            self.assertEqual(proof.current_password,bytearray(len(before)))
            self.assertEqual(proof.new_password,bytearray(len(after)))
