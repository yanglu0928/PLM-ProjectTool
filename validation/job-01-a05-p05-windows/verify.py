"""Actual two Windows factories against mixed committed Document and published Audit."""
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
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec

ROOT = Path(__file__).resolve().parents[1]
def load(name, folder):
    spec = spec_from_file_location(name, ROOT / folder / 'verify.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module

mixed = load('_windows_job_list_mixed', 'job-01-a05-p04-mixed')
old = load('_windows_job_list_old', 'job-01-a03-windows')

def observe(v):
    settings = BootstrapSettings(data_root=v['file_root'], trusted_origins=('http://localhost',))
    prefix = 'plm_assistant.entrypoints.production_login.'
    db = v['db']
    tables = ('job_jobs','job_outbox_events','job_leases','job_attempts','doc_upload_intents','doc_documents',
        'doc_document_versions','doc_version_source_refs','doc_file_objects','aud_events','plt_idempotency_receipts',
        'aud_exports','aud_export_acceptances','aud_export_results','auth_users','auth_sessions','prj_project_members','prj_departments')
    def snapshot():
        return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    contexts = ((f"/api/v1/projects/{v['project']}/jobs", v['tokens'][0], v['project']),
        ('/api/v1/admin/jobs', v['tokens'][1], None))
    with patch(prefix + 'read_database_url', return_value=v['url']):
        with ExitStack() as trust:
            trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services', return_value=SimpleNamespace(guard=v['guard'])))
            for name, codec in (
                ('create_windows_secret_list_cursor_codec', old.old.trust.SecretListCursorCodec(b'q'*32)),
                ('create_windows_project_member_cursor_codec', old.old.trust.MemberListCursorCodec(b'm'*32)),
                ('create_windows_project_department_cursor_codec', old.old.trust.DepartmentListCursorCodec(b'd'*32)),
                ('create_windows_document_list_cursor_codec', old.old.trust.DocumentListCursorCodec(b'l'*32)),
                ('create_windows_document_version_cursor_codec', old.old.trust.VersionListCursorCodec(b'v'*32)),
                ('create_windows_document_parse_cursor_codec', old.old.trust.ParseListCursorCodec(b'p'*32)),
                ('create_windows_audit_cursor_codec', old.old.trust.AuditListCursorCodec(b'a'*32)),
                ('create_windows_job_list_cursor_codec', JobListCursorCodec(b'j'*32)),
            ): trust.enter_context(patch(prefix + name, return_value=codec))
            trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service', return_value=object()))
            trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer', return_value=old.old.trust.HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32), key_ref='document-upload-token-v1')))
            for app in (create_app(), production.create_production_login_app(settings)):
                with TestClient(app, base_url='http://localhost') as client:
                    for path, token, pid in contexts:
                        assert client.get(path, headers={'cookie':'plm_session='+token.hex()}).status_code == 404
            for factory in (production.create_production_platform_app, production.create_production_platform_write_app):
                with TestClient(factory(settings), base_url='http://localhost') as client:
                    for path, token, pid in contexts:
                        before = snapshot(); items=[]; seen=set(); cursor=None
                        while True:
                            params={'page_size':2}
                            if cursor is not None: params['cursor']=cursor
                            response=client.get(path,params=params,headers={'cookie':'plm_session='+token.hex()})
                            assert response.status_code == 200
                            assert response.headers['cache-control']=='no-store'
                            data=response.json()['data']; items.extend(data['items'])
                            assert snapshot()==before
                            if not data['has_more']:
                                assert data['next_cursor'] is None; break
                            cursor=data['next_cursor']; assert cursor not in seen
                            seen.add(cursor); assert len(seen)<80
                        expected={str(row[0]) for row in db.execute("SELECT job_id FROM plm.job_jobs WHERE project_id IS NOT DISTINCT FROM %s AND owner_module IN ('audit','document')",(pid,))}
                        assert {item['job_id'] for item in items}==expected and len(items)==len(expected)
                        assert {item['owner_module'] for item in items}=={'audit','document'}
                        assert any(item['state']=='SUCCEEDED' and item['result_ref']['type']=='AUDIT_EXPORT' for item in items)
                        assert any(item['state']=='PENDING' and item['result_ref'] is None for item in items)
                        assert client.get(path,headers={'cookie':'plm_session='+(b'?'*32).hex()}).status_code==401
                        v['guard'].enabled=False
                        try: assert client.get(path,headers={'cookie':'plm_session='+token.hex()}).status_code==403
                        finally: v['guard'].enabled=True
                        assert snapshot()==before
                    assert client.get(contexts[0][0],headers={'cookie':'plm_session='+v['tokens'][1].hex()}).status_code==404
                    assert client.get(contexts[1][0],headers={'cookie':'plm_session='+v['tokens'][0].hex()}).status_code==401
                for dependency in ('create_windows_job_list_cursor_codec','AuthorizedJobListService','create_job_list_router'):
                    before=snapshot()
                    with patch(prefix+dependency,side_effect=RuntimeError('private failure')) as failed:
                        try: factory(settings)
                        except production.ProductionLoginStartupError as exc: assert 'private' not in str(exc)
                        else: raise AssertionError('Partial runtime returned')
                        failed.assert_called_once()
                    assert snapshot()==before
        for factory in (production.create_production_platform_app, production.create_production_platform_write_app):
            before=snapshot()
            try: factory(settings)
            except production.ProductionLoginStartupError: pass
            else: raise AssertionError('Formal trust unexpectedly available')
            assert snapshot()==before
    print('Windows Job list PASS: both actual factories, mixed published Audit/committed Document, current Session/Scope/License, encrypted pagination complete without duplicates, eighteen tables unchanged; default/login404, three explicit dependency faults per factory and actual absent formal trust refuse startup. Positive trust injected; no formal key provision/Parser/performance/three-platform/package/Gate claim.')

if __name__ == '__main__': mixed.fixture.main(exercise=lambda v: mixed.exercise(v, observe_runtime=observe))
