"""Own authenticated atomic password change; no License or Admin requirement."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID,uuid4
from .user_read import _id,_time
from .password_change_actor import PasswordChangeActorProof
from .password_change_result import PasswordChangeResult
from .password_change_replay import PasswordChangeProof,PasswordChangeReplayError
from .ports.password_hash import PasswordHashResult
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyScope,IdempotencyResult,IdempotencyError,validate_idempotency_key,canonical_payload_fingerprint)


class PasswordChangeError(RuntimeError):
    def __init__(self,code='AUTH_PASSWORD_CHANGE_UNAVAILABLE'):
        self.code=code if type(code) is str and code in ('AUTH_PASSWORD_CHANGE_UNAVAILABLE',
            'VALIDATION_FAILED','AUTH_ACCESS_DENIED','AUTH_INVALID_CREDENTIALS','CONFLICT_IDEMPOTENCY') else 'AUTH_PASSWORD_CHANGE_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True,slots=True)
class ChangePassword:
    session_token:bytes=field(repr=False)
    csrf_token:bytes=field(repr=False)
    trace_id:UUID
    passwords:PasswordChangeProof=field(repr=False)


class PasswordChangeService:
    def __init__(self,*,unit_of_work,access,repository,results,replay_verifier,hasher,audit,receipts,clock=None):
        if any(x is None for x in (unit_of_work,access,repository,results,replay_verifier,hasher,audit,receipts)):
            raise ValueError('Actual atomic password change dependencies required')
        self._uow,self._access,self._repo=unit_of_work,access,repository
        self._results,self._replay,self._hasher=results,replay_verifier,hasher
        self._audit,self._receipts=audit,receipts
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def _now(self):
        now=self._clock()
        if not _time(now):raise PasswordChangeError()
        return now

    def _actor(self,tx,command):
        proof=self._access.prove(tx,session_token=command.session_token,csrf_token=command.csrf_token,now=self._now())
        if proof is None:raise PasswordChangeError('AUTH_ACCESS_DENIED')
        if type(proof) is not PasswordChangeActorProof:raise PasswordChangeError()
        proof.__post_init__()
        return proof

    def change(self,command,*,idempotency_key):
        try:
            if (type(command) is not ChangePassword or not _id(command.trace_id)
                or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))
                or type(command.passwords) is not PasswordChangeProof):raise PasswordChangeError('VALIDATION_FAILED')
            for secret in (command.passwords.current_password,command.passwords.new_password):
                if type(secret) is not bytearray or not 1<=len(secret)<=1024 or b'\x00' in secret:
                    raise PasswordChangeError('VALIDATION_FAILED')
                try:secret.decode('utf-8',errors='strict')
                except UnicodeDecodeError:raise PasswordChangeError('VALIDATION_FAILED') from None
            validate_idempotency_key(idempotency_key)
            fingerprint=canonical_payload_fingerprint({'request_schema':1})
            op='V1_AUTH_PASSWORD_CHANGE'
            with self._uow() as tx:
                if self._access.lock_deployment(tx) is not True:raise PasswordChangeError()
                proof=self._actor(tx,command);actor=proof.user_view.user_id
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=None,operation=op,key=idempotency_key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type!=op or replay.status_code!=200:
                        raise PasswordChangeError()
                    result=self._results.get(tx,result_id=replay.ref_id)
                    if type(result) is not PasswordChangeResult or result.user_id!=actor or result.result_id!=replay.ref_id:
                        raise PasswordChangeError()
                    result.__post_init__()
                    if self._replay.require_match(tx,result=result,proof=command.passwords)!=result:
                        raise PasswordChangeError()
                    if self._actor(tx,command)!=proof:raise PasswordChangeError('AUTH_ACCESS_DENIED')
                    return result
                with memoryview(command.passwords.current_password) as password:
                    matched=self._access.verify_current_password(tx,proof=proof,password=password)
                if matched is False:raise PasswordChangeError('AUTH_INVALID_CREDENTIALS')
                if matched is not True:raise PasswordChangeError()
                with memoryview(command.passwords.new_password) as password:hashed=self._hasher.hash_password(password)
                if type(hashed) is not PasswordHashResult:raise PasswordChangeError()
                credential_id,changed_at,count=self._repo.change(tx,proof=proof,password_hash=hashed)
                if not _id(credential_id) or not _time(changed_at) or type(count) is not int or count<1:
                    raise PasswordChangeError()
                before=proof.user_view
                event=self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,event_scope='DEPLOYMENT',
                    target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
                    action='PASSWORD_CHANGED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
                    target_object_id=actor,before_state=f'CREDENTIAL_V{before.credential_version}',
                    after_state=f'CREDENTIAL_V{before.credential_version+1}'))
                draft=PasswordChangeResult(uuid4(),actor,proof.credential_id,credential_id,
                    before.credential_version,before.credential_version+1,before.lock_version,before.lock_version+1,
                    event,command.trace_id,count,changed_at,changed_at)
                result=self._results.record(tx,draft=draft)
                if type(result) is not PasswordChangeResult:raise PasswordChangeError()
                result.__post_init__()
                if any(getattr(result,k)!=getattr(draft,k) for k in draft.__dataclass_fields__ if k!='accepted_at'):
                    raise PasswordChangeError()
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(op,result.result_id,200))
                if self._access.require_changed(tx,proof=proof,result=result,session_token=command.session_token,
                    csrf_token=command.csrf_token,trace_id=command.trace_id,now=self._now()) is not True:
                    raise PasswordChangeError('AUTH_ACCESS_DENIED')
                tx.commit()
                return result
        except PasswordChangeError:raise
        except (PasswordChangeReplayError,IdempotencyError) as exc:raise PasswordChangeError(exc.code) from None
        except Exception:raise PasswordChangeError() from None
        finally:
            if type(command) is ChangePassword and type(command.passwords) is PasswordChangeProof:
                command.passwords.erase()
