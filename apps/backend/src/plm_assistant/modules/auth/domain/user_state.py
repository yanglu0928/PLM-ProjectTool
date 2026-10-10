"""Pure User state decisions, not current authority or database locking proof."""
from dataclasses import dataclass

MAX_VERSION = 9223372036854775807


class UserStateRuleError(ValueError):
    def __init__(self, code='AUTH_STATE_UNAVAILABLE'):
        self.code = code if type(code) is str and code in (
            'AUTH_STATE_UNAVAILABLE', 'VALIDATION_FAILED', 'CONFLICT_STATE', 'CONFLICT_VERSION'
        ) else 'AUTH_STATE_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class UserStateTransition:
    before_state: str
    after_state: str
    next_version: int
    revoke_all_sessions: bool
    audit_action: str


def decide_user_state(*, operation, state, deployment_role, credential_version,
                      has_active_credential, lock_version, expected_version,
                      other_enabled_admins):
    """Inputs must be freshly loaded under the eventual Application state lock.

    No actor/Session/License proof is accepted here; callers must enforce those
    independently. Other-admin count excludes target and includes only enabled
    identities. An authorized self-disable is not blanket forbidden.
    """
    if (type(operation) is not str or operation not in ('ENABLE','DISABLE')
        or type(state) is not str or state not in ('ENABLED','DISABLED')
        or type(deployment_role) is not str or deployment_role not in ('NONE','DEPLOYMENT_ADMIN')
        or type(has_active_credential) is not bool
        or any(type(v) is not int or not 0 <= v <= MAX_VERSION for v in
               (credential_version,lock_version,expected_version,other_enabled_admins))):
        raise UserStateRuleError('VALIDATION_FAILED')
    if (credential_version == 0) == has_active_credential or state == 'ENABLED' and credential_version == 0:
        raise UserStateRuleError()
    if lock_version != expected_version or lock_version == MAX_VERSION:
        raise UserStateRuleError('CONFLICT_VERSION')
    before, after = ('DISABLED','ENABLED') if operation == 'ENABLE' else ('ENABLED','DISABLED')
    if state != before or operation == 'ENABLE' and credential_version == 0:
        raise UserStateRuleError('CONFLICT_STATE')
    if operation == 'DISABLE' and deployment_role == 'DEPLOYMENT_ADMIN' and other_enabled_admins == 0:
        raise UserStateRuleError('CONFLICT_STATE')
    return UserStateTransition(before,after,lock_version+1,operation=='DISABLE',
        'USER_ENABLED' if operation=='ENABLE' else 'USER_DISABLED')
