"""Read-only current Windows account source for the dedicated opaque Job-list key."""
from typing import Protocol
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider

JOB_LIST_CURSOR_KEY_REF = 'job-list-cursor-v1'


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionJobListCursorStartupError(RuntimeError):
    def __init__(self): super().__init__('Job list cursor key unavailable')


def create_windows_job_list_cursor_codec(*, resolver: CursorKeyResolverPort | None = None) -> JobListCursorCodec:
    try:
        source = WindowsSecretKeyProvider() if resolver is None else resolver
        return JobListCursorCodec(source.resolve_key(JOB_LIST_CURSOR_KEY_REF))
    except Exception:
        raise ProductionJobListCursorStartupError() from None
