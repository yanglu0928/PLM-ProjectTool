"""Atomic current-admin User state changes and immutable first response replay."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID
from .user_read import UserReadView,_id,_time
from .user_state_result import UserStateResult
from ..domain.user_state import UserStateRuleError
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyScope,IdempotencyResult,IdempotencyError,validate_idempotency_key,canonical_payload_fingerprint)


class UserStateError(RuntimeError):
    def __init__(self,code='AUTH_STATE_UNAVAILABLE'):
        self.code=code if type(code) is str and code in ('AUTH_STATE_UNAVAILABLE','VALIDATION_FAILED',
            'AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','CONFLICT_STATE','CONFLICT_VERSION',
            'CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED') else 'AUTH_STATE_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True,slots=True)
class ChangeUserState:
    session_token:bytes=field(repr=False)
    csrf_token:bytes=field(repr=False)
    trace_id:UUID
    user_id:UUID
    expected_version:int


@dataclass(frozen=True,slots=True)
class UserStateActorProof:
    user_view:UserReadView
    credential_id:UUID
    session_id:UUID
    session_version:int
    session_created_at:datetime
    session_idle_expires_at:datetime
    session_absolute_expires_at:datetime
    def __post_init__(self):
        try:
            if type(self.user_view) is not UserReadView:raise UserStateError()
            self.user_view.__post_init__()
            if (self.user_view.account_state!='ENABLED' or self.user_view.deployment_role!='DEPLOYMENT_ADMIN'
                or not _id(self.credential_id) or not _id(self.session_id)
                or type(self.session_version) is not int or not 0<=self.session_version<=9223372036854775807
                or any(not _time(v) for v in (self.session_created_at,self.session_idle_expires_at,self.session_absolute_expires_at))
                or not self.session_created_at<self.session_idle_expires_at<=self.session_absolute_expires_at):
                raise UserStateError()
        except Exception:raise UserStateError() from None


class UserStateService:
    def __init__(self,*,unit_of_work,access,repository,results,audit,receipts,license_guard,clock=None):
        if any(v is None for v in (unit_of_work,access,repository,results,audit,receipts,license_guard)):
            raise ValueError('Actual atomic User state dependencies required')
        self._uow,self._access,self._repo=unit_of_work,access,repository
        self._results,self._audit,self._receipts,self._guard=results,audit,receipts,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def enable(self,command,*,idempotency_key):return self._execute(command,'ENABLE',idempotency_key)
    def disable(self,command,*,idempotency_key):return self._execute(command,'DISABLE',idempotency_key)

    def _now(self):
        now=self._clock()
        if not _time(now):raise UserStateError()
        return now

    def _actor(self,tx,command):
        proof=self._access.prove(tx,session_token=command.session_token,csrf_token=command.csrf_token,now=self._now())
        if proof is None:raise UserStateError('AUTH_ACCESS_DENIED')
        if type(proof) is not UserStateActorProof:raise UserStateError()
        proof.__post_init__()
        return proof

    def _final(self,tx,command,proof,result,*,changed):
        self._guard.require_valid(trace_id=command.trace_id)
        if changed and result.operation=='DISABLE' and proof.user_view.user_id==command.user_id:
            if self._access.require_self_disabled(tx,proof=proof,command=command,result=result,now=self._now()) is not True:
                raise UserStateError('AUTH_ACCESS_DENIED')
        elif self._actor(tx,command)!=proof:raise UserStateError('AUTH_ACCESS_DENIED')

    @staticmethod
    def _result(result,command,operation,actor):
        if type(result) is not UserStateResult:raise UserStateError()
        result.__post_init__()
        if (result.first_view.user_id!=command.user_id or result.actor_id!=actor
            or result.operation!=operation or result.expected_version!=command.expected_version):raise UserStateError()

    def _execute(self,command,operation,key):
        try:
            if (type(command) is not ChangeUserState or not _id(command.trace_id) or not _id(command.user_id)
                or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))
                or type(command.expected_version) is not int or not 0<=command.expected_version<9223372036854775807):
                raise UserStateError('VALIDATION_FAILED')
            validate_idempotency_key(key)
            fingerprint=canonical_payload_fingerprint({'user_id':str(command.user_id),
                'expected_version':command.expected_version,'request_schema':1})
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                if self._access.lock_deployment(tx) is not True:
                    raise UserStateError()
                proof=self._actor(tx,command);actor=proof.user_view.user_id
                op='V1_AUTH_USER_'+operation
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=None,operation=op,key=key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type!=op or replay.status_code!=200:
                        raise UserStateError()
                    result=self._results.get(tx,result_id=replay.ref_id)
                    self._result(result,command,operation,actor)
                    if result.result_id!=replay.ref_id:
                        raise UserStateError()
                    self._final(tx,command,proof,result,changed=False)
                    return result
                view,before,count=self._repo.change(tx,user_id=command.user_id,
                    expected_version=command.expected_version,operation=operation,actor_id=actor)
                if (type(view) is not UserReadView or before!=('DISABLED' if operation=='ENABLE' else 'ENABLED')
                    or view.user_id!=command.user_id or view.lock_version!=command.expected_version+1
                    or view.account_state!=('ENABLED' if operation=='ENABLE' else 'DISABLED')
                    or type(count) is not int or not 0<=count<=9223372036854775807
                    or operation=='ENABLE' and count!=0):
                    raise UserStateError()
                view.__post_init__()
                event=self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,event_scope='DEPLOYMENT',
                    target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
                    action='USER_ENABLED' if operation=='ENABLE' else 'USER_DISABLED',outcome='SUCCESS',
                    target_owner_module='auth',target_object_type='AUT-01',target_object_id=command.user_id,
                    before_state=before,after_state=view.account_state))
                if not _id(event):
                    raise UserStateError()
                result=self._results.record(tx,view=view,actor_id=actor,audit_event_id=event,
                    trace_id=command.trace_id,operation=operation,expected_version=command.expected_version,
                    revoked_session_count=count)
                self._result(result,command,operation,actor)
                if (result.first_view!=view or result.audit_event_id!=event or result.trace_id!=command.trace_id
                    or result.revoked_session_count!=count):
                    raise UserStateError()
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(op,result.result_id,200))
                self._final(tx,command,proof,result,changed=True)
                tx.commit()
                return result
        except UserStateError:raise
        except (UserStateRuleError,IdempotencyError) as exc:raise UserStateError(exc.code) from None
        except RuntimeLicenseError:raise UserStateError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise UserStateError() from None
