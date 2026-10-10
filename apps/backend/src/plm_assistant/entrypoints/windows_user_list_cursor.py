"""Current Windows account read-only dedicated User list cursor key source."""
from typing import Protocol
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider

USER_LIST_CURSOR_KEY_REF='user-list-cursor-v1'


class CursorKeyResolverPort(Protocol):
    def resolve_key(self,key_ref:str)->bytes|None: ...


class ProductionUserListCursorStartupError(RuntimeError):
    def __init__(self):super().__init__('User list cursor key unavailable')


def create_windows_user_list_cursor_codec(*,resolver:CursorKeyResolverPort|None=None)->UserListCursorCodec:
    try:
        source=WindowsSecretKeyProvider() if resolver is None else resolver
        return UserListCursorCodec(source.resolve_key(USER_LIST_CURSOR_KEY_REF))
    except Exception:raise ProductionUserListCursorStartupError() from None
