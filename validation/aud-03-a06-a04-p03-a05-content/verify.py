"""Actual current Sessions/success sources/private snapshots; no HTTP here."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from dataclasses import replace
from uuid import uuid4
import hashlib
from psycopg import sql
from plm_assistant.modules.audit.application.export_content import AuditExportContentReader,AuditExportContentQuery,PrepareAuditExportContent
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadError
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

load=spec_from_file_location('_content_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
f=module_from_spec(load);load.loader.exec_module(f)


def exercise(v):
    reader=AuditExportContentReader(unit_of_work=v['uow'],project_access=SqlAlchemyProjectReadAccess(),deployment_access=SqlAlchemyDeploymentReadAccess(),
        projects=v['projects'],license_guard=v['guard'],repository=v['repo'],results=v['results'],plans=v['deps']['plans'],
        files=v['files'],completion=v['completion'],audit=v['audit'])
    db=v['db'];snapshots=[]
    class Storage:
        after=None
        def open_snapshot(self,content):
            assert v['active'][0]==0
            stream=v['actual'].open_snapshot(content);snapshots.append(stream)
            if self.after:self.after()
            return stream
    storage=Storage();service=PrepareAuditExportContent(reader=reader,storage=storage)
    tables=('aud_export_results','doc_file_objects','doc_file_state_events','job_jobs','job_leases','job_attempts','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def denied(q,code):
        try:service.prepare(q)
        except AuthorizedAuditReadError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unauthorized/corrupt content accepted')
    exported=[]
    for scope in ('PROJECT','DEPLOYMENT'):
        for count in (0,260):
            accepted,c,staged=v['prepare'](scope,count)
            result=v['worker'].publish(c,staged)
            q=AuditExportContentQuery(v['tokens'][0 if scope=='PROJECT' else 1],v['project'] if scope=='PROJECT' else None,uuid4(),c.export_id)
            before=snapshot()
            with service.prepare(q) as output:
                assert output.detected_mime=='application/x-ndjson' and output.size_bytes==result.byte_count
                blob=output.stream.read();assert len(blob.splitlines())==count and hashlib.sha256(blob).digest()==result.file_sha256
                assert not hasattr(output,'locator') and not hasattr(output,'worker_ref')
            assert snapshots[-1].closed and snapshot()==before
            exported.append((q,c,staged,result))
    q,c,staged,result=exported[1]
    for query,code in ((replace(q,session_token=b'X'*32),'AUTH_ACCESS_DENIED'),
                       (replace(q,session_token=v['tokens'][1]),'RESOURCE_NOT_FOUND'),
                       (replace(q,project_id=None,session_token=v['tokens'][1]),'RESOURCE_NOT_FOUND'),
                       (replace(q,export_id=uuid4()),'RESOURCE_NOT_FOUND'),
                       (replace(exported[-1][0],project_id=v['project'],session_token=v['tokens'][0]),'RESOURCE_NOT_FOUND')):
        before=snapshot();count=len(snapshots);denied(query,code);assert snapshot()==before and len(snapshots)==count
    v['guard'].enabled=False;denied(q,'LICENSE_OPERATION_DENIED');v['guard'].enabled=True
    # Reauthorization after full snapshot; no bytes reach caller when current facts change.
    revoke_token=b'R'*32
    revoke_actor=f.base.auth.user(db,'Synthetic export revoked reader',revoke_token,'NONE')
    f.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=revoke_actor,department_id=v['dept'],project_role='PROJECT_MANAGER'),'project_member_id')
    revoke_q=replace(q,session_token=revoke_token)
    def revoke():db.execute("UPDATE plm.auth_sessions SET revoked_at=clock_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE session_token_digest=%s",(hashlib.sha256(revoke_token).digest(),))
    storage.after=revoke;denied(revoke_q,'AUTH_ACCESS_DENIED');assert snapshots[-1].closed;storage.after=None
    # Use a new current PM Session; published source actor is historical, not caller auth.
    new_token=b'N'*32
    new_actor=f.base.auth.user(db,'Synthetic export replacement PM',new_token,'NONE')
    f.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=new_actor,department_id=v['dept'],project_role='PROJECT_MANAGER'),'project_member_id')
    new_q=replace(q,session_token=new_token)
    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
    before=snapshot()
    with service.prepare(new_q) as output:assert hashlib.sha256(output.stream.read()).digest()==result.file_sha256
    assert snapshot()==before
    # Bad content: current authorized caller produces one safe failure Audit; history preserved.
    path=v['file_root']/f.f._locators(staged.content.coordinate)[1];original=path.read_bytes();path.write_bytes(original+b'corrupt')
    events_before=db.execute('SELECT count(*) FROM plm.aud_events').fetchone()[0]
    denied(new_q,'AUDIT_EXPORT_CONTENT_UNAVAILABLE')
    assert db.execute('SELECT count(*) FROM plm.aud_events').fetchone()[0]==events_before+1
    assert db.execute("SELECT actor_id,reason_code FROM plm.aud_events WHERE action='AUDIT_EXPORT_DOWNLOAD_CONTENT_FAILED' AND trace_id=%s",(new_q.trace_id,)).fetchone()==(new_actor,'FILE_CONTENT_UNAVAILABLE')
    assert db.execute('SELECT file_sha256 FROM plm.aud_export_results WHERE export_id=%s',(c.export_id,)).fetchone()[0]==result.file_sha256
    path.write_bytes(original)
    # Do not leave fixture's original submitter disabled for subsequent regression cases.
    db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
    # Dedicated reader Session stays revoked; original submitter Session was untouched.
    print('P03-A05 PASS: real accepted published sources/Job success/current PM or Admin Session -> private verified snapshot dualScope empty/260; hash/copy outside UOW, safe no-Locator stream/close/read-no-writes; missing/wrong Session/Admin project bypass/crossScope/missing export/License reject before file I/O, snapshot-after-revoke closed; current replacement PM can read history of disabled original actor; corrupt file safe authorized failure Audit, success history preserved. License synthetic; HTTP/stream lifecycle limits/large Worker dataset performance and platform production proof require remaining checks; 128MiB adapter boundary verified separately in unit suite.')


if __name__=='__main__':f.main(exercise=exercise)
