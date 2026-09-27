"""Current-admin atomic creation; non-secret receipt plus original-password replay proof."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from .user_read import _id, _time
from .user_create_result import UserCreateResult
from .user_create_replay import UserCreatePasswordProof, UserCreateReplayError
from .ports.password_hash import PasswordHashResult
from ..domain.username import normalize_username, UsernameValidationError
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key)

OPERATION='V1_AUTH_USER_CREATE'


class ManagedUserCreateError(RuntimeError):
    def __init__(self, code='AUTH_CREATE_UNAVAILABLE'):
        self.code=code if type(code) is str and code in ('AUTH_CREATE_UNAVAILABLE','VALIDATION_FAILED',
            'AUTH_ACCESS_DENIED','AUTH_USERNAME_CONFLICT','CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED') else 'AUTH_CREATE_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class CreateManagedUser:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: UUID
    username: str
    password: bytearray = field(repr=False)


class ManagedUserCreateService:
    def __init__(self, *, unit_of_work, access, license_guard, users, results, replay_verifier,
                 hasher, audit, receipts, clock=None):
        if any(v is None for v in (unit_of_work,access,license_guard,users,results,replay_verifier,hasher,audit,receipts)):
            raise ValueError('Actual atomic User creation dependencies required')
        self._uow,self._access,self._guard=unit_of_work,access,license_guard
        self._users,self._results,self._replay=users,results,replay_verifier
        self._hasher,self._audit,self._receipts=hasher,audit,receipts
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def create(self, command, *, idempotency_key):
        password=command.password if type(command) is CreateManagedUser else None
        try:
            username=self._prepare(command)
            validate_idempotency_key(idempotency_key)
            # Deliberately NOT a complete request proof: replay additionally requires original password.
            fingerprint=canonical_payload_fingerprint({'username_display':username.display,
                'username_normalized':username.normalized,'request_schema':1})
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor=self._actor(tx,command)
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=None,operation=OPERATION,key=idempotency_key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if type(replay) is not IdempotencyResult or replay.ref_type!=OPERATION or replay.status_code!=201:
                        raise ManagedUserCreateError()
                    result=self._results.get(tx,user_id=replay.ref_id)
                    self._check_result(result,actor,username.display)
                    if result.first_view.user_id!=replay.ref_id:raise ManagedUserCreateError()
                    proven=self._replay.require_match(tx,result=result,proof=UserCreatePasswordProof(password))
                    if proven!=result:raise ManagedUserCreateError()
                    self._final(tx,command,actor)
                    return result.first_view
                view=memoryview(password)
                try:hashed=self._hasher.hash_password(view)
                finally:view.release()
                self._check_hash(hashed)
                user=self._users.add_user(tx,username_display=username.display,
                    username_normalized=username.normalized,actor_id=actor)
                if user is None:raise ManagedUserCreateError('AUTH_USERNAME_CONFLICT')
                if not _id(user):raise ManagedUserCreateError()
                credential=self._users.add_credential(tx,user_id=user,password_hash=hashed,actor_id=actor)
                if not _id(credential) or self._users.activate_initial_credential(
                    tx,user_id=user,credential_id=credential,actor_id=actor) is not True:
                    raise ManagedUserCreateError()
                event=self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,event_scope='DEPLOYMENT',
                    target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,
                    actor_hint_digest=None,action='USER_CREATED',outcome='SUCCESS',target_owner_module='auth',
                    target_object_type='AUT-01',target_object_id=user,after_state='ENABLED'))
                if not _id(event):raise ManagedUserCreateError()
                result=self._results.record(tx,user_id=user,credential_id=credential,actor_id=actor,
                    audit_event_id=event,trace_id=command.trace_id)
                self._check_result(result,actor,username.display)
                if (result.first_view.user_id!=user or result.credential_id!=credential
                    or result.audit_event_id!=event or result.trace_id!=command.trace_id):raise ManagedUserCreateError()
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(OPERATION,user,201))
                self._final(tx,command,actor)
                tx.commit()
                return result.first_view
        except ManagedUserCreateError:raise
        except (IdempotencyError,UserCreateReplayError) as exc:
            raise ManagedUserCreateError(exc.code) from None
        except RuntimeLicenseError:raise ManagedUserCreateError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise ManagedUserCreateError() from None
        finally:
            if type(password) is bytearray:password[:]=b'\x00'*len(password)

    @staticmethod
    def _prepare(command):
        if (type(command) is not CreateManagedUser or not _id(command.trace_id)
            or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))
            or type(command.password) is not bytearray or not 1<=len(command.password)<=1024
            or b'\x00' in command.password):raise ManagedUserCreateError('VALIDATION_FAILED')
        try:
            command.password.decode('utf-8',errors='strict')
            return normalize_username(command.username)
        except (UsernameValidationError,UnicodeDecodeError):raise ManagedUserCreateError('VALIDATION_FAILED') from None

    def _actor(self,tx,command):
        now=self._clock()
        if not _time(now):raise ManagedUserCreateError()
        actor=self._access.authorized_admin(tx,session_token=command.session_token,
            csrf_token=command.csrf_token,now=now)
        if not _id(actor):raise ManagedUserCreateError('AUTH_ACCESS_DENIED')
        return actor

    def _final(self,tx,command,actor):
        self._guard.require_valid(trace_id=command.trace_id)
        if self._actor(tx,command)!=actor:raise ManagedUserCreateError('AUTH_ACCESS_DENIED')

    @staticmethod
    def _check_result(result,actor,display):
        if type(result) is not UserCreateResult:raise ManagedUserCreateError()
        result.__post_init__()
        if result.actor_id!=actor or result.first_view.username_display!=display:raise ManagedUserCreateError()

    @staticmethod
    def _check_hash(hashed):
        if (type(hashed) is not PasswordHashResult or type(hashed.algorithm_id) is not str or hashed.algorithm_id!='SCRYPT'
            or type(hashed.password_hash) is not str or not 1<=len(hashed.password_hash)<=1024
            or type(hashed.parameter_set) is not dict or not 1<=len(hashed.parameter_set)<=16
            or any(type(k) is not str or not k.isascii() or not k.isidentifier()
                or type(v) is not int or not 0<=v<=1_000_000_000 for k,v in hashed.parameter_set.items())):
            raise ManagedUserCreateError()
