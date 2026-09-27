import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.jobs.api.list_jobs import create_job_list_router
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.jobs.application.authorized_list import JobListPage
from plm_assistant.modules.jobs.application.authorized_read import JobDetail, JobReadFacts, JobOwnerProjection, JobReadError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


class JobListApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.job = uuid4(), uuid4()
        self.facts = JobReadFacts(self.job, 'document', 'DOCUMENT_PARSE', 'PROJECT', self.project, uuid4(), 'PENDING', 0, datetime.now(timezone.utc), None)
        self.reads = Mock(); self.reads.list.return_value = JobListPage((JobDetail(self.facts, JobOwnerProjection(self.job, False)),), None, False)
        self.codec = JobListCursorCodec(b'k' * 32)
        self.client = TestClient(create_app(job_list_router=create_job_list_router(reads=self.reads,
            origins=LoginOriginPolicy(['https://plm.example.test']), cursors=self.codec)), base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path = f'/api/v1/projects/{self.project}/jobs'
        self.headers = {'cookie': 'plm_session=' + (b's' * 32).hex()}

    def test_safe_list_envelope_no_store_and_opaque_empty_page(self):
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {'data', 'trace_id'})
        data = response.json()['data']
        self.assertEqual(set(data), {'items', 'next_cursor', 'has_more'})
        self.assertEqual(data['items'][0]['job_id'], str(self.job))
        self.assertEqual(response.headers['cache-control'], 'no-store')
        for hidden in ('payload_refs', 'actor_id', 'worker_ref', 'storage_locator', 'fencing_token'):
            self.assertNotIn(hidden, data['items'][0])
        self.reads.list.return_value = JobListPage((), (self.facts.created_at, self.job), True)
        data = self.client.get(self.path, headers=self.headers).json()['data']
        self.assertEqual(data['items'], []); self.assertTrue(data['has_more'])
        token = data['next_cursor']
        self.assertEqual(self.client.get(self.path + '?cursor=' + token, headers=self.headers).status_code, 200)
        self.assertEqual(self.reads.list.call_args.args[0].before, (self.facts.created_at, self.job))

    def test_strict_query_and_browser_boundaries_before_service(self):
        for query, code in (('?page_size=0', 422), ('?page_size=201', 422), ('?page_size=01', 422),
            ('?page_size=1&page_size=2', 400), ('?unknown=1', 400), ('?scope=GLOBAL', 422), ('?cursor=bad', 400)):
            self.assertEqual(self.client.get(self.path + query, headers=self.headers).status_code, code)
        self.assertEqual(self.client.get(self.path, headers=dict(self.headers, host='evil.test')).status_code, 403)
        self.assertEqual(self.client.get(self.path).status_code, 401)
        self.reads.list.assert_not_called()

    def test_error_mapping_and_private_exception_not_returned(self):
        for code, status in (('AUTH_ACCESS_DENIED', 401), ('RESOURCE_NOT_FOUND', 404), ('LICENSE_OPERATION_DENIED', 403), ('JOB_UNAVAILABLE', 503)):
            self.reads.list.side_effect = JobReadError(code)
            response = self.client.get(self.path, headers=self.headers)
            self.assertEqual(response.status_code, status)
        self.reads.list.side_effect = RuntimeError('private SQL/path')
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 503); self.assertNotIn('private', response.text)

    def test_default_closed_cross_project_projection_refused(self):
        with TestClient(create_app()) as default: self.assertEqual(default.get(self.path).status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/projects/{uuid4()}/jobs', headers=self.headers).status_code, 503)
        self.reads.list.return_value = object()
        self.assertEqual(self.client.get(self.path, headers=self.headers).status_code, 503)
