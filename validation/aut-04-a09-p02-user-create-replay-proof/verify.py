"""Actual immutable first Credential1 + real fixed Scrypt; no create HTTP authority."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from dataclasses import replace
from unittest.mock import patch
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import text
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher,PARAMETERS
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.application.session_service import PasswordIssueProof
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.user_create_replay import (
    UserCreateReplayVerifier,UserCreatePasswordProof,UserCreateReplayError)

spec=spec_from_file_location('_user_replay_publication',Path(__file__).resolve().parents[1]
    /'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];actor=v['users'][1];repo=SqlAlchemyUserRepository();hasher=ScryptPasswordHasher()
    source=SqlAlchemyUserCreateResultRepository(verifier=hasher)
    verifier=UserCreateReplayVerifier(source=source)
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events',
            'plt_idempotency_receipts','auth_user_create_results')
    def snapshot():
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def hash_secret(text):
        secret=bytearray(text.encode());view=memoryview(secret)
        try:return hasher.hash_password(view)
        finally:view.release();secret[:]=b'\x00'*len(secret)
    original='  合成凭据-é-first  '
    original_hash=hash_secret(original)
    def make_result(label,hashed):
        trace=uuid4()
        with v['uow']() as tx:
            user=repo.add_user(tx,username_display=label,username_normalized=label.lower(),actor_id=actor)
            credential=repo.add_credential(tx,user_id=user,password_hash=hashed,actor_id=actor)
            assert repo.activate_initial_credential(tx,user_id=user,credential_id=credential,actor_id=actor)
            event=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
                target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
                action='USER_CREATED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
                target_object_id=user,after_state='ENABLED'))
            # Schema insertion in same caller transaction, no production create Service yet.
            tx.session.execute(text("""INSERT INTO plm.auth_user_create_results(
                user_id,credential_id,actor_id,audit_event_id,trace_id,username_display,account_state,
                deployment_role,credential_version,lock_version,created_at,updated_at)
                SELECT user_id,:credential,:actor,:event,:trace,username_display,state,deployment_role,
                credential_version,lock_version,created_at,updated_at FROM plm.auth_users WHERE user_id=:user"""),
                dict(credential=credential,actor=actor,event=event,trace=trace,user=user))
            tx.commit()
        with v['uow']() as tx:result=source.get(tx,user_id=user)
        assert result is not None and result.actor_id==actor
        return result
    result=make_result('Synthetic real replay first',original_hash)
    before=snapshot()
    with v['uow']() as tx:
        assert source.get(tx,user_id=uuid4()) is None
        assert source.get(tx,user_id=v['users'][0]) is None # No invented backfill.
        proof=PasswordIssueProof(bytearray(original.encode()))
        try:assert SqlAlchemyPasswordIssueAccess(hasher).can_issue(tx,result.first_view.user_id,1,proof) is True
        finally:proof.erase()
    assert snapshot()==before
    def match(text,expected=None,selected=result):
        before=snapshot();proof=UserCreatePasswordProof(bytearray(text.encode()))
        try:
            with v['uow']() as tx:
                actual=verifier.require_match(tx,result=selected,proof=proof)
                assert expected is None and actual==selected
        except UserCreateReplayError as exc:
            assert exc.code==expected,(exc.code,expected)
        finally:assert not any(proof.password)
        assert snapshot()==before
    match(original)
    for wrong in ('Wrong synthetic input',original.strip(),original.replace('é','e\u0301')):
        match(wrong,'CONFLICT_IDEMPOTENCY')
    for changed in (replace(result,credential_id=uuid4()),replace(result,actor_id=uuid4()),
                    replace(result,trace_id=uuid4()),replace(result,audit_event_id=uuid4()),
                    replace(result,first_view=replace(result.first_view,username_display='Forged first name'))):
        match(original,'AUTH_CREATE_REPLAY_UNAVAILABLE',changed)
    # Legitimate immutable version2 fixture, not a password reset implementation.
    newer=hash_secret('Synthetic current credential2')
    credential2=fixture.base.schema.insert(db,'auth_password_credentials',dict(user_id=result.first_view.user_id,
        credential_version=2,password_hash=newer.password_hash,algorithm_id=newer.algorithm_id,
        parameter_set=Jsonb(dict(newer.parameter_set)),must_change_password=False,changed_by=actor),
        'password_credential_id')
    db.execute("UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=2,state='DISABLED',"
        "username_display='Synthetic later renamed',updated_at=statement_timestamp(),lock_version=2 WHERE user_id=%s",
        (credential2,result.first_view.user_id))
    with v['uow']() as tx:assert source.get(tx,user_id=result.first_view.user_id)==result
    match(original);match('Synthetic current credential2','CONFLICT_IDEMPOTENCY')
    # Fault in real KDF resources is unavailable, not password conflict; no writes/erasure proven.
    with patch('hashlib.scrypt',side_effect=ValueError('Synthetic private OpenSSL detail')):
        match(original,'AUTH_CREATE_REPLAY_UNAVAILABLE')
    for index,bad in enumerate((PasswordHashResult(original_hash.password_hash,'TEST_ONLY',dict(PARAMETERS)),
        PasswordHashResult(original_hash.password_hash,'SCRYPT',PARAMETERS|{'p':True}),
        PasswordHashResult(original_hash.password_hash[:-1]+'z','SCRYPT',dict(PARAMETERS)))):
        broken=make_result('Synthetic bad replay source '+str(index),bad)
        with patch('hashlib.scrypt',side_effect=AssertionError('Malformed source must not invoke KDF')):
            match(original,'AUTH_CREATE_REPLAY_UNAVAILABLE',broken)
    print('User replay proof PASS: actual fixed Scrypt/original Credential1+immutable first result, '
        'original password authentication proof, wrong/trim/NFC-different bytes conflict, forged coordinates '
        'unavailable; after target rename/disable/credential2 still original1 matches and current2 conflicts. '
        'Malformed source refuses before KDF, actual KDF fault unavailable, six full tables unchanged on '
        'all verification/refusal paths, caller proof erased. Current Admin-CSRF/License/full request '
        'receipt/atomic create/HTTP/runtime/performance/production/Gate/package NOT proven.')


if __name__=='__main__':fixture.main(exercise=exercise)
