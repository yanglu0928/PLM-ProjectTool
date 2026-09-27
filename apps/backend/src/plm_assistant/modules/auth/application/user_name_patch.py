"""Current-admin name-only mutation; stable identity and credential history."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from .user_read import UserReadView, _id, _time
from ..domain.username import normalize_username, UsernameValidationError
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class UserNamePatchError(RuntimeError):
    def __init__(self, code='AUTH_PATCH_UNAVAILABLE'):
        self.code = code if type(code) is str and code in (
            'AUTH_PATCH_UNAVAILABLE', 'VALIDATION_FAILED', 'AUTH_ACCESS_DENIED',
            'RESOURCE_NOT_FOUND', 'CONFLICT_VERSION', 'CONFLICT_DUPLICATE',
            'LICENSE_OPERATION_DENIED') else 'AUTH_PATCH_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class PatchUserName:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: UUID
    user_id: UUID
    expected_version: int
    username: str


class UserNamePatchService:
    def __init__(self, *, unit_of_work, access, repository, audit, license_guard, clock=None):
        if any(v is None for v in (unit_of_work, access, repository, audit, license_guard)):
            raise ValueError('Actual User name mutation dependencies required')
        self._uow, self._access, self._repo = unit_of_work, access, repository
        self._audit, self._guard = audit, license_guard
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _actor(self, tx, command):
        now = self._clock()
        if not _time(now):
            raise UserNamePatchError()
        actor = self._access.authorized_admin(tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now)
        if not _id(actor):
            raise UserNamePatchError('AUTH_ACCESS_DENIED')
        return actor

    def patch(self, command):
        try:
            if (type(command) is not PatchUserName or not _id(command.user_id)
                or not _id(command.trace_id)
                or any(type(v) is not bytes or len(v) != 32 for v in
                       (command.session_token, command.csrf_token))
                or type(command.expected_version) is not int
                or not 0 <= command.expected_version <= 9223372036854775807):
                raise UserNamePatchError('VALIDATION_FAILED')
            try:
                name = normalize_username(command.username)
            except UsernameValidationError:
                raise UserNamePatchError('VALIDATION_FAILED') from None
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                view, changed = self._repo.patch(tx, user_id=command.user_id,
                    expected_version=command.expected_version, username=name, actor_id=actor)
                if type(view) is not UserReadView or type(changed) is not bool:
                    raise UserNamePatchError()
                view.__post_init__()
                if (view.user_id != command.user_id or view.username_display != name.display
                    or view.lock_version != command.expected_version + int(changed)):
                    raise UserNamePatchError()
                if changed:
                    event = self._audit.append(tx, AuditEventDraft(trace_id=command.trace_id,
                        event_scope='DEPLOYMENT', target_project_id=None, actor_type='USER',
                        actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                        action='USER_NAME_CHANGED', outcome='SUCCESS', target_owner_module='auth',
                        target_object_type='AUT-01', target_object_id=command.user_id,
                        before_state=view.account_state, after_state=view.account_state))
                    if not _id(event):
                        raise UserNamePatchError()
                self._guard.require_valid(trace_id=command.trace_id)
                if self._actor(tx, command) != actor:
                    raise UserNamePatchError('AUTH_ACCESS_DENIED')
                if changed:
                    tx.commit()
                return view
        except UserNamePatchError:
            raise
        except RuntimeLicenseError:
            raise UserNamePatchError('LICENSE_OPERATION_DENIED') from None
        except Exception:
            raise UserNamePatchError() from None
