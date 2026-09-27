"""Atomic current-admin reset with immutable first and exact self final proof."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID,uuid4
from threading import BoundedSemaphore
from .user_read import UserReadView,_id,_time
from .user_state import UserStateActorProof
from .password_reset_result import PasswordResetResult
from .password_reset_replay import PasswordResetProof,PasswordResetReplayError
from .ports.password_hash import PasswordHashResult
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyScope,IdempotencyResult,IdempotencyError,validate_idempotency_key,canonical_payload_fingerprint)

# Process-local bound for reset preparation, not a credential or authority cache.
_RESET_HASH_SLOTS=BoundedSemaphore(4)


class _ResetReplayAppeared(Exception):
    """Internal bounded retry signal, only after the write UOW has rolled back."""


class PasswordResetError(RuntimeError):
    def __init__(self,code='AUTH_PASSWORD_RESET_UNAVAILABLE'):
        self.code=code if type(code) is str and code in ('AUTH_PASSWORD_RESET_UNAVAILABLE','VALIDATION_FAILED',
            'AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','CONFLICT_VERSION','CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED') else 'AUTH_PASSWORD_RESET_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True,slots=True)
class ResetPassword:
    session_token:bytes=field(repr=False)
    csrf_token:bytes=field(repr=False)
    trace_id:UUID
    user_id:UUID
    expected_version:int
    must_change_password:bool
    password:PasswordResetProof=field(repr=False)


class PasswordResetService:
    def __init__(self,*,unit_of_work,access,repository,results,replay_verifier,hasher,audit,receipts,license_guard,clock=None,capacity=None):
        if any(x is None for x in (unit_of_work,access,repository,results,replay_verifier,hasher,audit,receipts,license_guard)):
            raise ValueError('Actual atomic password reset dependencies required')
        self._uow,self._access,self._repo=unit_of_work,access,repository
        self._results,self._replay,self._hasher=results,replay_verifier,hasher
        self._audit,self._receipts,self._guard=audit,receipts,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))
        self._capacity=capacity

    def _now(self):
        now=self._clock()
        if not _time(now):raise PasswordResetError()
        return now

    def _actor(self,tx,command):
        proof=self._access.prove(tx,session_token=command.session_token,csrf_token=command.csrf_token,now=self._now())
        if proof is None:raise PasswordResetError('AUTH_ACCESS_DENIED')
        if type(proof) is not UserStateActorProof:raise PasswordResetError()
        proof.__post_init__()
        return proof

    def _final(self,tx,command,proof,result,*,changed):
        self._guard.require_valid(trace_id=command.trace_id)
        if changed and command.user_id==proof.user_view.user_id:
            if self._access.require_self_reset(tx,proof=proof,result=result,session_token=command.session_token,
                csrf_token=command.csrf_token,trace_id=command.trace_id,expected_version=command.expected_version,
                now=self._now()) is not True:raise PasswordResetError('AUTH_ACCESS_DENIED')
        elif self._actor(tx,command)!=proof:raise PasswordResetError('AUTH_ACCESS_DENIED')

    @staticmethod
    def _result(result,command,actor):
        if type(result) is not PasswordResetResult:raise PasswordResetError()
        result.__post_init__()
        if result.user_id!=command.user_id or result.actor_id!=actor or result.before_user_version!=command.expected_version:
            raise PasswordResetError()

    def reset(self,command,*,idempotency_key):
        return self._reset(command,idempotency_key=idempotency_key,race_retry=False)

    def _reset(self,command,*,idempotency_key,race_retry):
        try:
            if (type(command) is not ResetPassword or not _id(command.trace_id) or not _id(command.user_id)
                or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))
                or type(command.expected_version) is not int or not 0<=command.expected_version<9223372036854775807
                or command.must_change_password is not True or type(command.password) is not PasswordResetProof):
                raise PasswordResetError('VALIDATION_FAILED')
            secret=command.password.temporary_password
            if type(secret) is not bytearray or not 1<=len(secret)<=1024 or b'\x00' in secret:
                raise PasswordResetError('VALIDATION_FAILED')
            try:secret.decode('utf-8',errors='strict')
            except UnicodeDecodeError:raise PasswordResetError('VALIDATION_FAILED') from None
            validate_idempotency_key(idempotency_key)
            fingerprint=canonical_payload_fingerprint({'user_id':str(command.user_id),'expected_version':command.expected_version,
                'must_change_password':True,'request_schema':1})
            op='V1_AUTH_USER_RESET_PASSWORD'
            self._guard.require_valid(trace_id=command.trace_id)
            # This short proof only gates expensive work. Its UOW must be closed
            # before hashing; the write UOW below obtains its own current proof.
            with self._uow() as preparation:
                prepared_proof=self._actor(preparation,command)
                prepared_scope=IdempotencyScope.from_key(actor_id=prepared_proof.user_view.user_id,
                    project_id=None,operation=op,key=idempotency_key)
                hint=self._receipts.lookup_completed(preparation,scope=prepared_scope,request_fingerprint=fingerprint)
                prepared_result=source=None
                if hint is not None:
                    if type(hint) is not IdempotencyResult or hint.ref_type!=op or hint.status_code!=200:
                        raise PasswordResetError()
                    prepared_result=self._results.get(preparation,result_id=hint.ref_id)
                    self._result(prepared_result,command,prepared_scope.actor_id)
                    if prepared_result.result_id!=hint.ref_id:raise PasswordResetError()
                    source=self._results.password_source(preparation,result=prepared_result)
                    if type(source) is not PasswordHashResult:raise PasswordResetError()
            capacity=self._capacity if self._capacity is not None else _RESET_HASH_SLOTS
            if capacity.acquire(timeout=5) is not True:raise PasswordResetError()
            try:
                hashed=None
                with memoryview(secret) as password:
                    if hint is None:
                        hashed=self._hasher.hash_password(password)
                        if type(hashed) is not PasswordHashResult:raise PasswordResetError()
                    else:
                        matched=self._results.verify_password_source(source=source,password=password)
                        if matched is False:raise PasswordResetError('CONFLICT_IDEMPOTENCY')
                        if matched is not True:raise PasswordResetError()
            finally:
                capacity.release()
            with self._uow() as tx:
                if self._access.lock_deployment(tx) is not True:raise PasswordResetError()
                proof=self._actor(tx,command);actor=proof.user_view.user_id
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=None,operation=op,key=idempotency_key)
                if scope!=prepared_scope:raise PasswordResetError('AUTH_ACCESS_DENIED')
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if hint is None:raise _ResetReplayAppeared()
                    if type(replay) is not IdempotencyResult or replay.ref_type!=op or replay.status_code!=200:
                        raise PasswordResetError()
                    result=self._results.get(tx,result_id=replay.ref_id);self._result(result,command,actor)
                    if replay!=hint or result!=prepared_result or result.result_id!=replay.ref_id:
                        raise PasswordResetError()
                    self._results.require_password_source(tx,result=result,source=source)
                    self._final(tx,command,proof,result,changed=False)
                    return result
                if hint is not None or type(hashed) is not PasswordHashResult:raise PasswordResetError()
                view,oldid,before,count,newid=self._repo.reset(tx,user_id=command.user_id,
                    expected_version=command.expected_version,actor_id=actor,password_hash=hashed)
                if type(view) is not UserReadView or type(before) is not UserReadView:raise PasswordResetError()
                view.__post_init__();before.__post_init__()
                if (view.user_id!=command.user_id or before.user_id!=command.user_id or before.lock_version!=command.expected_version
                    or view.lock_version!=before.lock_version+1 or view.credential_version!=before.credential_version+1
                    or view.updated_at<before.updated_at or not _id(oldid) or not _id(newid) or oldid==newid
                    or type(count) is not int or not 0<=count<=9223372036854775807
                    or any(getattr(view,k)!=getattr(before,k) for k in ('user_id','username_display','account_state','deployment_role','created_at'))):
                    raise PasswordResetError()
                event=self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,event_scope='DEPLOYMENT',
                    target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
                    action='PASSWORD_RESET',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
                    target_object_id=command.user_id,before_state=f'CREDENTIAL_V{before.credential_version}',
                    after_state=f'CREDENTIAL_V{view.credential_version}'))
                draft=PasswordResetResult(uuid4(),command.user_id,actor,oldid,newid,before.credential_version,
                    view.credential_version,before.lock_version,view.lock_version,view.account_state,event,command.trace_id,
                    count,view.updated_at,view.updated_at)
                result=self._results.record(tx,draft=draft);self._result(result,command,actor)
                if any(getattr(result,k)!=getattr(draft,k) for k in draft.__dataclass_fields__ if k!='accepted_at'):
                    raise PasswordResetError()
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(op,result.result_id,200))
                self._final(tx,command,proof,result,changed=True)
                tx.commit()
                return result
        except _ResetReplayAppeared:
            if race_retry:raise PasswordResetError() from None
            return self._reset(command,idempotency_key=idempotency_key,race_retry=True)
        except PasswordResetError:raise
        except (PasswordResetReplayError,IdempotencyError) as exc:raise PasswordResetError(exc.code) from None
        except RuntimeLicenseError:raise PasswordResetError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise PasswordResetError() from None
        finally:
            if type(command) is ResetPassword and type(command.password) is PasswordResetProof:command.password.erase()
