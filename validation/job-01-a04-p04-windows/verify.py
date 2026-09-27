"""Actual Windows factories for current Session and constrained parse metadata results."""
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings

ROOT = Path(__file__).resolve().parents[1]


def load(name, folder):
    spec = spec_from_file_location(name, ROOT / folder / 'verify.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module


results = load('_windows_parse_results', 'job-01-a04-p03-result-source')
authority = load('_windows_parse_authority', 'job-01-a04-p03-authority')
old = load('_windows_parse_previous_jobs', 'job-01-a03-windows')


def runtime_observer(v, queries):
    runtime_guard = authority.auth.Guard()
    settings = BootstrapSettings(data_root=v['root'], trusted_origins=('http://localhost',))
    prefix = 'plm_assistant.entrypoints.production_login.'
    tables = ('job_jobs', 'job_outbox_events', 'doc_upload_intents', 'doc_documents', 'doc_document_versions',
        'doc_version_source_refs', 'doc_file_objects', 'aud_events', 'plt_idempotency_receipts',
        'auth_users', 'auth_sessions', 'prj_project_members', 'prj_departments', 'doc_parse_records', 'doc_parse_result_refs')
    with results.base.fixture.connect(v['name']) as db:
        def snapshot(): return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        def path(q): return f'/api/v1/projects/{q.project_id}/jobs/{q.job_id}' if q.project_id else f'/api/v1/admin/jobs/{q.job_id}'
        with ExitStack() as credentials:
            credentials.enter_context(patch(prefix + 'read_database_url', return_value=v['url']))
            with ExitStack() as trust:
                trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services', return_value=SimpleNamespace(guard=runtime_guard)))
                for name, codec in (
                    ('create_windows_secret_list_cursor_codec', old.old.trust.SecretListCursorCodec(b'q' * 32)),
                    ('create_windows_project_member_cursor_codec', old.old.trust.MemberListCursorCodec(b'm' * 32)),
                    ('create_windows_project_department_cursor_codec', old.old.trust.DepartmentListCursorCodec(b'd' * 32)),
                    ('create_windows_document_list_cursor_codec', old.old.trust.DocumentListCursorCodec(b'l' * 32)),
                    ('create_windows_document_version_cursor_codec', old.old.trust.VersionListCursorCodec(b'v' * 32)),
                    ('create_windows_document_parse_cursor_codec', old.old.trust.ParseListCursorCodec(b'p' * 32)),
                    ('create_windows_audit_cursor_codec', old.old.trust.AuditListCursorCodec(b'a' * 32)),
                ): trust.enter_context(patch(prefix + name, return_value=codec))
                trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service', return_value=object()))
                trust.enter_context(patch(prefix + 'create_windows_document_upload_token_issuer', return_value=old.old.trust.HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref: b'u' * 32), key_ref='document-upload-token-v1')))
                for app in (create_app(), production.create_production_login_app(settings)):
                    with TestClient(app, base_url='http://localhost') as client:
                        for q in queries: assert client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex()}).status_code == 404
                for factory in (production.create_production_platform_app, production.create_production_platform_write_app):
                    with TestClient(factory(settings), base_url='http://localhost') as client:
                        for q in queries:
                            before = snapshot()
                            headers = {'cookie': 'plm_session=' + q.session_token.hex()}
                            response = client.get(path(q), headers=headers)
                            assert response.status_code == 200 and snapshot() == before
                            data = response.json()['data']
                            record = db.execute("SELECT parse_record_id FROM plm.doc_parse_records WHERE job_ref=%s AND parse_state='SUCCEEDED'", (q.job_id,)).fetchone()[0]
                            version = db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s', (q.job_id,)).fetchone()[0]
                            assert data['state'] == 'SUCCEEDED' and data['result_ref'] == {'type': 'DOCUMENT_PARSE', 'id': str(record)}
                            assert response.headers['etag'] == data['etag'] == f'"v{version}"'
                            assert response.headers['cache-control'] == 'no-store'
                            assert client.get(path(q), headers={'cookie': 'plm_session=' + (b'?' * 32).hex()}).status_code == 401
                            assert snapshot() == before
                        assert client.get(path(queries[0]), headers={'cookie': 'plm_session=' + queries[1].session_token.hex()}).status_code == 404
                        before = snapshot(); runtime_guard.enabled = False
                        try:
                            for q in queries: assert client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex()}).status_code == 403
                        finally: runtime_guard.enabled = True
                        assert snapshot() == before
                    for name in ('DocumentParseJobReadProjection', 'DocumentParseSourceReader', 'SqlAlchemyDocumentParseSources',
                        'DocumentParseJobResults', 'SqlAlchemyDocumentParseJobResults', 'UploadCommitAuditSources', 'SqlAlchemyUploadCommitAuditSources'):
                        before = snapshot()
                        with patch(prefix + name, side_effect=RuntimeError('private constructor detail')):
                            try: factory(settings)
                            except production.ProductionLoginStartupError as exc: assert 'private' not in str(exc)
                            else: raise AssertionError('Partial Document app returned')
                        assert snapshot() == before
            for factory in (production.create_production_platform_app, production.create_production_platform_write_app):
                before = snapshot()
                try: factory(settings)
                except production.ProductionLoginStartupError: pass
                else: raise AssertionError('Formal trust unexpectedly available; re-audit required')
                assert snapshot() == before
    print('Document Windows factories PASS: actual two explicit factories/current Session/PG successful logical ParseRecord source/ref, fifteen tables no read writes; default/login404, unknown Session/License/admin-project refusal, seven constructor faults and actual absent formal trust per factory refuse partial startup. Injected positive trust and directly seeded Parser history; no actual Parser/bytes/SCM/three-platform/package/Gate proof.')


if __name__ == '__main__':
    results.base.fixture.verify(exercise=lambda v: results.base.exercise(v, observe=lambda v, g:
        results.observe(v, g, observe_success=lambda v, g: authority.observe(v, g, runtime_observer=runtime_observer))))
