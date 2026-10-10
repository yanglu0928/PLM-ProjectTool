"""Fail-closed, read-only Windows current-account Audit cursor key source."""
from typing import Protocol
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec

AUDIT_CURSOR_KEY_REF="audit-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self,key_ref:str)->bytes|None:...


class ProductionAuditCursorStartupError(RuntimeError):
    def __init__(self):super().__init__("audit cursor key unavailable")


def create_windows_audit_cursor_codec(*,resolver:CursorKeyResolverPort|None=None)->AuditListCursorCodec:
    try:
        source=WindowsSecretKeyProvider() if resolver is None else resolver
        return AuditListCursorCodec(source.resolve_key(AUDIT_CURSOR_KEY_REF))
    except Exception:
        raise ProductionAuditCursorStartupError() from None
