"""Opt-in full verified JSONL; explicit ownership across cancelled thread awaits."""
import asyncio
import threading
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_read import AuthorizedAuditReadError
from ..application.export_content import AuditExportContentQuery, VerifiedAuditExportDownload
from .read_events import _error


class _SnapshotOwner:
    """A cancelled caller cannot release a still-running prepare/read worker's slot."""
    def __init__(self, slots):
        self.slots, self.lock = slots, threading.Lock()
        self.ready = None
        self.busy = self.abandoned = self.released = False

    def _cleanup(self):
        if self.released or self.busy:
            return
        self.released = True
        try:
            if self.ready is not None:
                self.ready.close()
        finally:
            self.slots.release()

    def abandon(self):
        with self.lock:
            self.abandoned = True
            self._cleanup()

    def prepare(self, downloads, query):
        with self.lock:
            if self.abandoned:
                return None
            self.busy = True
        value = None
        try:
            value = downloads.prepare(query)
            if type(value) is not VerifiedAuditExportDownload:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            if (type(value.export_id) is not UUID or value.export_id != query.export_id
                    or type(value.size_bytes) is not int or not 0 <= value.size_bytes <= 128*1024*1024
                    or type(value.content_sha256) is not bytes or len(value.content_sha256) != 32
                    or value.detected_mime != 'application/x-ndjson'
                    or not callable(getattr(value.stream, 'read', None))
                    or not callable(getattr(value.stream, 'close', None))):
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            return value
        finally:
            with self.lock:
                self.ready = value if isinstance(value, VerifiedAuditExportDownload) else None
                self.busy = False
                if self.abandoned:
                    self._cleanup()

    def read(self):
        with self.lock:
            if self.abandoned:
                raise RuntimeError('Audit export stream closed')
            self.busy = True
        try:
            return self.ready.stream.read(1_048_576)
        except Exception:
            raise RuntimeError('Audit export stream unavailable') from None
        finally:
            with self.lock:
                self.busy = False
                if self.abandoned:
                    self._cleanup()


async def _thread_owned(call):
    # shield keeps the thread-dispatch coroutine alive; the owner, not the task,
    # closes resources when its synchronous operation eventually finishes.
    task = asyncio.create_task(run_in_threadpool(call))
    def consume(done):
        if not done.cancelled():
            done.exception()
    task.add_done_callback(consume)
    return await asyncio.shield(task)


class _OwnedResponse(StreamingResponse):
    def __init__(self, *args, owner, **kwargs):
        self._owner = owner
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._owner.abandon()


def create_audit_export_download_router(*, downloads, origins, max_inflight=4):
    if (downloads is None or origins is None or type(max_inflight) is not int
            or not 1 <= max_inflight <= 20):
        raise ValueError('Bounded authorized export download dependencies required')
    router = APIRouter()
    slots = threading.BoundedSemaphore(max_inflight)

    async def content(request, project, export):
        headers = tuple(request.scope.get('headers', ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError('AUTH_CSRF_INVALID') from None
        token = _session_cookie(headers)
        if request.url.query or 'range' in request.headers or 'if-range' in request.headers:
            raise ApplicationError('REQUEST_MALFORMED')
        if not export.int or project is not None and not project.int:
            raise ApplicationError('RESOURCE_NOT_FOUND')
        query = AuditExportContentQuery(token, project, UUID(request.state.trace_id), export)
        if not slots.acquire(blocking=False):
            raise ApplicationError('SYSTEM_UNAVAILABLE')
        owner = _SnapshotOwner(slots)
        try:
            ready = await _thread_owned(lambda: owner.prepare(downloads, query))

            async def chunks():
                count = 0
                while True:
                    data = await _thread_owned(owner.read)
                    if type(data) is not bytes or len(data) > 1_048_576:
                        raise RuntimeError('Invalid audit export snapshot')
                    count += len(data)
                    if count > ready.size_bytes or not data and count != ready.size_bytes:
                        raise RuntimeError('Invalid audit export snapshot length')
                    if not data:
                        break
                    yield data

            return _OwnedResponse(chunks(), owner=owner, media_type='application/x-ndjson', headers={
                'Content-Length': str(ready.size_bytes),
                'Content-Disposition': f'attachment; filename="audit-export-{export}.jsonl"',
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            })
        except BaseException as exc:
            owner.abandon()
            if isinstance(exc, AuthorizedAuditReadError):
                if exc.code == 'AUDIT_EXPORT_CONTENT_UNAVAILABLE':
                    raise ApplicationError('FILE_CONTENT_UNAVAILABLE') from None
                raise _error(exc) from None
            if isinstance(exc, ApplicationError):
                raise
            if isinstance(exc, Exception):
                raise ApplicationError('SYSTEM_UNAVAILABLE') from None
            raise

    @router.get('/api/v1/projects/{project_id}/audit-exports/{export_id}/content')
    async def project_content(project_id: UUID, export_id: UUID, request: Request):
        return await content(request, project_id, export_id)

    @router.get('/api/v1/admin/audit-exports/{export_id}/content')
    async def deployment_content(export_id: UUID, request: Request):
        return await content(request, None, export_id)

    return router
