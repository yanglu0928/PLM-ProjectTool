"""Real PG publication/current Session -> opt-in metadata HTTP, no synthetic source."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.read_export_result import create_audit_export_result_router
from plm_assistant.modules.audit.application.export_content import AuditExportContentReader
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

load = spec_from_file_location('_result_http_fixture', Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture = module_from_spec(load); load.loader.exec_module(fixture)


def exercise(v):
    reader = AuditExportContentReader(unit_of_work=v['uow'], project_access=SqlAlchemyProjectReadAccess(),
        deployment_access=SqlAlchemyDeploymentReadAccess(), projects=v['projects'], license_guard=v['guard'],
        repository=v['repo'], results=v['results'], plans=v['deps']['plans'], files=v['files'],
        completion=v['completion'], audit=v['audit'])
    app = create_app(audit_export_result_router=create_audit_export_result_router(reads=reader,
        origins=LoginOriginPolicy(['https://plm.example.test'])))
    db = v['db']
    tables = ('aud_export_results','doc_file_objects','doc_file_state_events','job_jobs','job_leases','job_attempts','aud_events')
    def snapshot():
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with TestClient(app, base_url='https://plm.example.test') as client:
        for scope in ('PROJECT','DEPLOYMENT'):
            _, command, staged = v['prepare'](scope, 260)
            result = v['worker'].publish(command, staged)
            path = (f'/api/v1/projects/{v["project"]}/audit-exports/{command.export_id}' if scope=='PROJECT'
                    else f'/api/v1/admin/audit-exports/{command.export_id}')
            token = v['tokens'][0 if scope=='PROJECT' else 1]
            cookie = {'cookie':'plm_session='+token.hex()}
            before = snapshot()
            response = client.get(path, headers=cookie)
            assert response.status_code==200, response.text
            body = response.json()['data']
            assert body['scope']==scope and body['size_bytes']==result.byte_count
            assert body['file_sha256']==result.file_sha256.hex()
            assert body['manifest_sha256']==result.manifest_sha256.hex()
            assert set(body)=={'export_id','scope','project_id','published_at','size_bytes','mime_type','file_sha256','manifest_version','manifest_sha256'}
            assert snapshot()==before and response.headers['cache-control']=='no-store'
            assert client.get(path, headers={'cookie':'plm_session='+(b'X'*32).hex()}).status_code==401
            assert client.get(path+'?x=1', headers=cookie).status_code==400
            if scope=='PROJECT':
                assert client.get(path, headers={'cookie':'plm_session='+v['tokens'][1].hex()}).status_code==404
                assert client.get(f'/api/v1/admin/audit-exports/{command.export_id}', headers={'cookie':'plm_session='+v['tokens'][1].hex()}).status_code==404
            else:
                assert client.get(f'/api/v1/projects/{v["project"]}/audit-exports/{command.export_id}', headers={'cookie':'plm_session='+v['tokens'][0].hex()}).status_code==404
            v['guard'].enabled=False
            assert client.get(path, headers=cookie).status_code==403
            v['guard'].enabled=True
            assert snapshot()==before
        assert client.get(f'/api/v1/admin/audit-exports/{uuid4()}', headers=cookie).status_code==404
    print('P03-A06-P01 PASS: actual dualScope published success sources -> current Session/PM or Admin HTTP metadata; exact safe projection/hash, no-store, wrong Session/Scope/Admin project bypass/License/query/missing source rejected; reads no business writes. License synthetic; content lifecycle/production composition/three-platform/package remain unverified.')


if __name__=='__main__':
    fixture.main(exercise=exercise)
