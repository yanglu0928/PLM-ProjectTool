"""Current immutable credential fact; identity is not business authorization."""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionCredentialFact:
    user_id: UUID
    session_id: UUID
    credential_id: UUID
    credential_version: int
    password_change_required: bool

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.user_id,self.session_id,self.credential_id))
            or type(self.credential_version) is not int or not 1<=self.credential_version<=9223372036854775807
            or type(self.password_change_required) is not bool):
            raise ValueError('Current Session credential unavailable')

    def permits(self, capability):
        if type(capability) is not str or capability not in (
            'PASSWORD_STATE','PASSWORD_CHANGE','LOGOUT','BUSINESS'):
            return False
        self.__post_init__()
        return capability != 'BUSINESS' or self.password_change_required is False
