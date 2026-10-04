"""Original true Session/Scope/source/keyset list matrix through optional encrypted-cursor HTTP."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.jobs.api.list_jobs import create_job_list_router
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.jobs.application.authorized_read import JobReadError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy

spec = spec_from_file_location('_list_http_current_sources', Path(__file__).resolve().parents[1] / 'job-01-a05-list' / 'verify.py')
fixture = module_from_spec(spec); spec.loader.exec_module(fixture)


def observe(v, queries):
    constructor = fixture.AuthorizedJobListService
    clients = []; counts = {'success': 0, 'refused': 0, 'empty_continuation': 0}
    class ThroughHttp:
        def __init__(self, actual):
            self.actual = actual; self.codec = JobListCursorCodec(b'J' * 32)
            self.client = TestClient(create_app(job_list_router=create_job_list_router(reads=actual,
                origins=LoginOriginPolicy(['https://plm.example.test']), cursors=self.codec)), base_url='https://plm.example.test')
            clients.append(self.client)

        def list(self, q):
            path = f'/api/v1/projects/{q.project_id}/jobs' if q.project_id else '/api/v1/admin/jobs'
            params = {'page_size': str(q.page_size)}
            if q.scope is not None: params['scope'] = q.scope
            if q.before is not None: params['cursor'] = self.codec.encode(query=q, before=q.before)
            response = self.client.get(path, params=params, headers={'cookie': 'plm_session=' + q.session_token.hex()})
            try: page = self.actual.list(q)
            except JobReadError as exc:
                assert response.status_code == {'AUTH_ACCESS_DENIED': 401, 'RESOURCE_NOT_FOUND': 404, 'LICENSE_OPERATION_DENIED': 403}.get(exc.code, 503)
                assert set(response.json()) == {'error', 'trace_id'}
                counts['refused'] += 1
                raise
            assert response.status_code == 200
            data = response.json()['data']
            assert [item['job_id'] for item in data['items']] == [str(item.facts.job_id) for item in page.items]
            assert data['has_more'] == page.has_more
            assert response.headers['cache-control'] == 'no-store'
            assert 'next_position' not in data and 'total_count' not in data
            if page.has_more:
                assert self.codec.decode(data['next_cursor'], query=q) == page.next_position
                if not page.items:
                    assert str(page.next_position[1]) not in response.text
                    counts['empty_continuation'] += 1
                assert self.client.get(path, params=dict(params, cursor=data['next_cursor'], page_size=str(q.page_size + 1)),
                    headers={'cookie': 'plm_session=' + q.session_token.hex()}).status_code == 400
            else: assert data['next_cursor'] is None
            counts['success'] += 1
            return page
    fixture.AuthorizedJobListService = lambda **kwargs: ThroughHttp(constructor(**kwargs))
    try:
        fixture.observe(v, queries)
        assert counts['success'] >= 12 and counts['refused'] >= 8 and counts['empty_continuation'] >= 1, counts
        with TestClient(create_app()) as default: assert default.get('/api/v1/admin/jobs').status_code == 404
        print('JOB list HTTP PASS: actual current Session/Project/Admin/Doc source/keyset matrix, encrypted continuation including empty hidden page, query-bound page-size tamper refusal/no raw position/default404 and no-write original checks; counts=' + str(counts) + '. Test key/License/credentials; no Windows key/runtime/Audit mixed list/performance/package/Gate proof.')
    finally:
        fixture.AuthorizedJobListService = constructor
        for client in clients: client.close()


if __name__ == '__main__':
    fixture.authority.base.fixture.verify(exercise=lambda v: fixture.authority.base.exercise(v,
        observe=lambda v, g: fixture.authority.observe(v, g, runtime_observer=observe)))
