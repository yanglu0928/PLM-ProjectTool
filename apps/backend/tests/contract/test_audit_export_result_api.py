from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.read_export_result import create_audit_export_result_router
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from unit import test_audit_export_content as content_fixture


class AuditExportResultApiTests(TestCase):
    def setUp(self):
        fixture = content_fixture.AuditExportContentTests(); fixture.setUp()
        self.source = fixture.source
        self.reader = Mock(); self.reader.get_source.return_value = self.source
        router = create_audit_export_result_router(reads=self.reader,
            origins=LoginOriginPolicy(['https://plm.example.test']))
        self.client = TestClient(create_app(audit_export_result_router=router), base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path = f'/api/v1/admin/audit-exports/{self.source.result.export_id}'
        self.cookie = 'plm_session=' + (b's'*32).hex()

    def get(self, path=None, **kwargs):
        return self.client.get(path or self.path, headers={'cookie':self.cookie, **kwargs})

    def test_default_closed_and_exact_safe_projection(self):
        with TestClient(create_app()) as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        data = response.json()['data']
        self.assertEqual(set(data), {'export_id','scope','project_id','published_at','size_bytes','mime_type',
                                     'file_sha256','manifest_version','manifest_sha256'})
        self.assertEqual(data['scope'], 'DEPLOYMENT'); self.assertIsNone(data['project_id'])
        self.assertEqual(data['file_sha256'], self.source.result.file_sha256.hex())
        self.assertEqual(self.reader.get_source.call_args.args[0].session_token, b's'*32)
        self.assertNotIn('manifest_bytes', response.text)

    def test_project_binding_rejects_wrong_source_and_accepts_matching(self):
        project = uuid4()
        path = f'/api/v1/projects/{project}/audit-exports/{self.source.result.export_id}'
        self.assertEqual(self.get(path).status_code, 503)
        content = replace(self.source.content, coordinate=replace(self.source.content.coordinate, scope='PROJECT', project_id=project))
        self.reader.get_source.return_value = replace(self.source, content=content)
        self.assertEqual(self.get(path).json()['data']['project_id'], str(project))

    def test_request_rejections_before_reader(self):
        for path, headers, status in (
            (self.path+'?cursor=x', {}, 400),
            (f'/api/v1/admin/audit-exports/{UUID(int=0)}', {}, 404),
            (self.path, {'cookie':'plm_session=bad'}, 401),
            (self.path, {'cookie':self.cookie+'; '+self.cookie}, 401),
            (self.path, {'host':'untrusted.test'}, 403),
        ):
            with self.subTest(path=path, headers=headers):
                self.assertEqual(self.get(path, **headers).status_code, status)
        self.reader.get_source.assert_not_called()

    def test_safe_exception_and_error_mapping(self):
        for error, expected in (
            (AuthorizedAuditReadError('AUTH_ACCESS_DENIED'),401),
            (AuthorizedAuditReadError('RESOURCE_NOT_FOUND'),404),
            (AuthorizedAuditReadError('LICENSE_OPERATION_DENIED'),403),
            (RuntimeError('private vault path'),503),
        ):
            self.reader.get_source.side_effect = error
            response = self.get()
            self.assertEqual(response.status_code, expected)
            self.assertNotIn('private vault', response.text)
        self.reader.get_source.side_effect = None
        self.reader.get_source.return_value = object()
        self.assertEqual(self.get().status_code, 503)
