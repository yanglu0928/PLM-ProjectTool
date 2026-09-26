import asyncio
import io
import threading
from unittest import TestCase
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.download_export import create_audit_export_download_router
from plm_assistant.modules.audit.application.export_content import VerifiedAuditExportDownload
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


class Downloads:
    def __init__(self):
        self.calls = 0; self.streams = []; self.entered = self.release = None
        self.factory = lambda: io.BytesIO(b'{"safe":true}\n')
        self.error = None; self.mime = 'application/x-ndjson'; self.size = 14

    def prepare(self, q):
        self.calls += 1
        if self.entered:
            self.entered.set(); self.release.wait(timeout=5)
        if self.error: raise self.error
        stream = self.factory(); self.streams.append(stream)
        return VerifiedAuditExportDownload(q.export_id, self.size, b'h'*32, stream, self.mime)


class AuditExportDownloadApiTests(TestCase):
    def setUp(self):
        self.downloads = Downloads()
        router = create_audit_export_download_router(downloads=self.downloads, max_inflight=1,
            origins=LoginOriginPolicy(['https://plm.example.test']))
        self.app = create_app(audit_export_download_router=router)
        self.client = TestClient(self.app, base_url='https://plm.example.test'); self.addCleanup(self.client.close)
        self.export = uuid4(); self.path = f'/api/v1/admin/audit-exports/{self.export}/content'
        self.cookie = 'plm_session='+(b's'*32).hex()

    def get(self, path=None, **headers):
        return self.client.get(path or self.path, headers={'cookie':self.cookie, **headers})

    async def request(self, send):
        async def receive():
            await asyncio.Event().wait()
        scope = dict(type='http', asgi={'version':'3.0','spec_version':'2.4'}, http_version='1.1',
            method='GET', scheme='https', path=self.path, raw_path=self.path.encode(), query_string=b'', root_path='',
            headers=[(b'host',b'plm.example.test'),(b'cookie',self.cookie.encode())],
            client=('127.0.0.1',1234), server=('plm.example.test',443))
        await self.app(scope, receive, send)

    def test_default_closed_and_full_headers(self):
        with TestClient(create_app()) as bare:self.assertEqual(bare.get(self.path).status_code,404)
        response = self.get()
        self.assertEqual(response.status_code,200); self.assertEqual(response.content,b'{"safe":true}\n')
        self.assertEqual(response.headers['content-length'],'14')
        self.assertEqual(response.headers['content-type'],'application/x-ndjson')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        self.assertEqual(response.headers['content-disposition'],f'attachment; filename="audit-export-{self.export}.jsonl"')
        self.assertTrue(self.downloads.streams[-1].closed)
        self.assertEqual(self.get(f'/api/v1/projects/{uuid4()}/audit-exports/{self.export}/content').status_code,200)

    def test_invalid_requests_and_safe_preparation_errors(self):
        for path, headers, status in ((self.path+'?x=1',{},400),(self.path,{'range':'bytes=0-1'},400),
            (self.path,{'if-range':'old'},400),(self.path,{'cookie':'bad'},401),(self.path,{'host':'bad.test'},403)):
            self.assertEqual(self.get(path,**headers).status_code,status)
        self.assertEqual(self.downloads.calls,0)
        for code,status in (('AUTH_ACCESS_DENIED',401),('RESOURCE_NOT_FOUND',404),('LICENSE_OPERATION_DENIED',403),('AUDIT_EXPORT_CONTENT_UNAVAILABLE',503)):
            self.downloads.error = AuthorizedAuditReadError(code)
            self.assertEqual(self.get().status_code,status)
        self.downloads.error = RuntimeError('private path')
        self.assertNotIn('private path',self.get().text)
        self.downloads.error = None; self.downloads.mime='bad\r\nheader'
        self.assertEqual(self.get().status_code,503); self.assertTrue(self.downloads.streams[-1].closed)
        self.downloads.mime='application/x-ndjson'; self.assertEqual(self.get().status_code,200)

    def test_start_and_body_send_failure_close_and_release(self):
        for failure in ('http.response.start','http.response.body'):
            async def send(message):
                if message['type']==failure:raise OSError('synthetic disconnect')
            with self.assertRaises(Exception):asyncio.run(self.request(send))
            self.assertTrue(self.downloads.streams[-1].closed)
            self.assertEqual(self.get().status_code,200)

    def test_bad_length_and_read_failure_close_and_release(self):
        self.downloads.size=1
        with self.assertRaises(Exception):self.get()
        self.assertTrue(self.downloads.streams[-1].closed)
        self.downloads.size=14
        class BadStream(io.BytesIO):
            def read(self,*args):raise OSError('private disk path')
        self.downloads.factory=BadStream
        with self.assertRaises(Exception):self.get()
        self.assertTrue(self.downloads.streams[-1].closed)
        self.downloads.factory=lambda:io.BytesIO(b'{"safe":true}\n')
        self.assertEqual(self.get().status_code,200)

    def test_cancel_while_response_start_waiting_closes_unstarted_generator(self):
        async def scenario():
            started=asyncio.Event()
            async def send(message):
                if message['type']=='http.response.start':
                    started.set();await asyncio.Event().wait()
            task=asyncio.create_task(self.request(send))
            await asyncio.wait_for(started.wait(),3)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertTrue(self.downloads.streams[-1].closed)
        asyncio.run(scenario())
        self.assertEqual(self.get().status_code,200)

    def _cancel_while_thread_busy(self, read=False):
        entered, release = threading.Event(), threading.Event()
        if read:
            class BlockingStream(io.BytesIO):
                def read(self,*args):
                    entered.set(); release.wait(timeout=5)
                    return super().read(*args)
            self.downloads.factory=lambda:BlockingStream(b'{"safe":true}\n')
        else:self.downloads.entered,self.downloads.release=entered,release
        async def scenario():
            async def send(message):pass
            task=asyncio.create_task(self.request(send))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait,3))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
                # The physically active thread still owns the sole slot.
                self.assertEqual(await asyncio.to_thread(lambda:self.get().status_code),503)
                if read:self.assertFalse(self.downloads.streams[-1].closed)
            finally:release.set()
            for _ in range(200):
                if self.downloads.streams and self.downloads.streams[-1].closed:break
                await asyncio.sleep(.01)
            self.assertTrue(self.downloads.streams[-1].closed)
        asyncio.run(scenario())
        self.downloads.entered=None
        self.downloads.factory=lambda:io.BytesIO(b'{"safe":true}\n')
        self.assertEqual(self.get().status_code,200)

    def test_cancel_during_preparation_does_not_abandon_thread_or_slot(self):
        self._cancel_while_thread_busy()

    def test_cancel_during_read_does_not_close_under_running_thread(self):
        self._cancel_while_thread_busy(read=True)
