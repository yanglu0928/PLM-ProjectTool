"""Actual published bytes/current auth -> HTTP; local synthetic data only."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
import hashlib
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.download_export import create_audit_export_download_router
from plm_assistant.modules.audit.application.export_content import AuditExportContentReader, PrepareAuditExportContent
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

load = spec_from_file_location('_download_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture = module_from_spec(load); load.loader.exec_module(fixture)


def exercise(v):
    reader=AuditExportContentReader(unit_of_work=v['uow'],project_access=SqlAlchemyProjectReadAccess(),
        deployment_access=SqlAlchemyDeploymentReadAccess(),projects=v['projects'],license_guard=v['guard'],
        repository=v['repo'],results=v['results'],plans=v['deps']['plans'],files=v['files'],completion=v['completion'],audit=v['audit'])
    class Storage:
        after=None
        streams=[]
        def open_snapshot(self, content):
            assert v['active'][0]==0
            stream=v['actual'].open_snapshot(content); self.streams.append(stream)
            if self.after:self.after()
            return stream
    storage=Storage()
    downloads=PrepareAuditExportContent(reader=reader,storage=storage)
    app=create_app(audit_export_download_router=create_audit_export_download_router(downloads=downloads,
        origins=LoginOriginPolicy(['https://plm.example.test']),max_inflight=1))
    db=v['db']; exported=[]
    tables=('aud_export_results','doc_file_objects','doc_file_state_events','job_jobs','job_leases','job_attempts','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with TestClient(app,base_url='https://plm.example.test') as client:
        for scope in ('PROJECT','DEPLOYMENT'):
            for count in (0,260):
                _,command,staged=v['prepare'](scope,count);result=v['worker'].publish(command,staged)
                path=(f'/api/v1/projects/{v["project"]}/audit-exports/{command.export_id}/content' if scope=='PROJECT'
                    else f'/api/v1/admin/audit-exports/{command.export_id}/content')
                cookie={'cookie':'plm_session='+v['tokens'][0 if scope=='PROJECT' else 1].hex()}
                before=snapshot(); response=client.get(path,headers=cookie)
                assert response.status_code==200,response.text
                assert len(response.content.splitlines())==count and hashlib.sha256(response.content).digest()==result.file_sha256
                assert len(response.content)==int(response.headers['content-length'])==result.byte_count
                assert response.headers['content-type']=='application/x-ndjson' and response.headers['cache-control']=='no-store'
                assert storage.streams[-1].closed and snapshot()==before
                copied=len(storage.streams)
                assert client.get(path,headers={'cookie':'plm_session='+(b'X'*32).hex()}).status_code==401
                v['guard'].enabled=False;assert client.get(path,headers=cookie).status_code==403;v['guard'].enabled=True
                if scope=='PROJECT':
                    assert client.get(path,headers={'cookie':'plm_session='+v['tokens'][1].hex()}).status_code==404
                    assert client.get(f'/api/v1/admin/audit-exports/{command.export_id}/content',headers={'cookie':'plm_session='+v['tokens'][1].hex()}).status_code==404
                else:
                    assert client.get(f'/api/v1/projects/{v["project"]}/audit-exports/{command.export_id}/content',headers={'cookie':'plm_session='+v['tokens'][0].hex()}).status_code==404
                assert len(storage.streams)==copied and snapshot()==before
                exported.append((path,cookie,command,staged))
        path,cookie,command,staged=exported[1]
        token=b'R'*32
        actor=fixture.base.auth.user(db,'Synthetic download revoked PM',token,'NONE')
        fixture.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=actor,department_id=v['dept'],project_role='PROJECT_MANAGER'),'project_member_id')
        def revoke():db.execute("UPDATE plm.auth_sessions SET revoked_at=clock_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE session_token_digest=%s",(hashlib.sha256(token).digest(),))
        storage.after=revoke;before=snapshot()
        response=client.get(path,headers={'cookie':'plm_session='+token.hex()})
        assert response.status_code==401 and storage.streams[-1].closed and snapshot()==before
        storage.after=None
        file=v['file_root']/fixture.f._locators(staged.content.coordinate)[1]
        original=file.read_bytes();file.write_bytes(original+b'corrupt')
        before=db.execute('SELECT count(*) FROM plm.aud_events').fetchone()[0]
        try:
            response=client.get(path,headers=cookie)
            assert response.status_code==503 and response.json()['error']['code']=='FILE_CONTENT_UNAVAILABLE'
            assert db.execute('SELECT count(*) FROM plm.aud_events').fetchone()[0]==before+1
            assert client.get(path,headers={'cookie':'plm_session='+(b'X'*32).hex()}).status_code==401
            assert db.execute('SELECT count(*) FROM plm.aud_events').fetchone()[0]==before+1
        finally:file.write_bytes(original)
        assert client.get(path,headers=cookie).status_code==200
    print('P03-A06-P02 PASS: actual published dualScope empty/260 JSONL HTTP exact bytes/full hash/headers/closed snapshots, current Session/PM or Admin/Scope/License deny before I/O; actual copy-after-revoke returns safe 401 closes snapshot and writes nothing; corrupted file returns FILE_CONTENT_UNAVAILABLE with one authorized Audit, unauthorized access no Audit; slot reusable. Cancellation/send/read failure capacity tests run separately. License synthetic; production composition/proxy disconnect/three-platform/performance/installer remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
