"""Actual Document sources and reversible isolated database boundary fixtures."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4, UUID
from datetime import timedelta

ROOT=Path(__file__).resolve().parents[1]
spec=spec_from_file_location('_retry_windows_matrix',ROOT/'job-03-a02-p05-windows-retry'/'verify.py')
windows=module_from_spec(spec);spec.loader.exec_module(windows)
mixed=windows.old.mixed

def matrix(v,client,command,path,headers,snapshot):
    db=v['db']; project=command.scope=='PROJECT'; index=0 if project else 1
    if 'retry_documents' not in v:v['retry_documents']=mixed.prepare_documents(v)
    original=v['retry_documents'][index]
    docpath=(f'/api/v1/projects/{command.project_id}/jobs/{original.parse_job_id}' if project
        else f'/api/v1/admin/jobs/{original.parse_job_id}')
    csrf=windows.http.atomic.worker.fixture.base.auth.CSRF.hex()
    write=headers|{'origin':'https://plm.example.test','x-csrf-token':csrf,
        'idempotency-key':str(uuid4()),'if-match':f'"v{command.expected_version}"'}
    def get(url=path,status=200,retryable=None,h=headers):
        before=snapshot();r=client.get(url,headers=h)
        assert r.status_code==status,(r.status_code,status,r.text)
        assert snapshot()==before
        if retryable is not None:assert r.json()['data']['retryable'] is retryable,r.text
        return r
    def reject(url=path+':retry',h=write,status=409,code='JOB_NOT_RETRYABLE'):
        before=snapshot();r=client.post(url,json={},headers=h)
        assert r.status_code==status,(r.status_code,status,r.text)
        assert r.json()['error']['code']==code,r.text
        assert snapshot()==before
    d=get(docpath,retryable=False)
    reject(docpath+':retry',h=write|{'if-match':d.headers['etag']})
    # These edits are reversible isolated technical fixtures, not a legitimate
    # Worker permanent failure or a production repair. Every HTTP check is read-only.
    attempt=db.execute('SELECT attempt_id,error_code,completed_at FROM plm.job_attempts WHERE job_id=%s AND attempt_no=3',
        (command.job_id,)).fetchone()
    try:
        db.execute("UPDATE plm.job_attempts SET error_code='LICENSE_OPERATION_DENIED' WHERE attempt_id=%s",(attempt[0],))
        get(retryable=False);reject()
    finally:db.execute('UPDATE plm.job_attempts SET error_code=%s WHERE attempt_id=%s',(attempt[1],attempt[0]))
    try:
        db.execute('UPDATE plm.job_attempts SET completed_at=%s WHERE attempt_id=%s',(attempt[2]+timedelta(seconds=1),attempt[0]))
        r=get(status=503);assert r.json()['error']['code']=='SYSTEM_UNAVAILABLE'
        reject(status=503,code='SYSTEM_UNAVAILABLE')
    finally:db.execute('UPDATE plm.job_attempts SET completed_at=%s WHERE attempt_id=%s',(attempt[2],attempt[0]))
    get(retryable=True)
    if project:
        for role in ('IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER'):
            db.execute('UPDATE plm.prj_project_members SET project_role=%s WHERE project_id=%s AND user_id=%s',
                (role,command.project_id,v['users'][0]))
            try:
                get(retryable=False)
                reject(status=404,code='RESOURCE_NOT_FOUND')
            finally:db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE project_id=%s AND user_id=%s",
                (command.project_id,v['users'][0]))
        token=b'c'*32
        customer=mixed.fixture.base.auth.user(db,'Synthetic retry noncreator',token,'NONE')
        mixed.fixture.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=customer,
            department_id=v['dept'],project_role='CUSTOMER_MEMBER'),'project_member_id')
        h=headers|{'cookie':'plm_session='+token.hex()}
        get(status=404,h=h);reject(h=write|h,status=404,code='RESOURCE_NOT_FOUND')
        # Frozen Audit maintenance exception: archived still permits PM export.
        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s",(command.project_id,))
        try:
            get(retryable=True)
            r=client.post(path+':retry',json={},headers=write|{'idempotency-key':str(uuid4())})
            assert r.status_code==202,r.text
            data=r.json()['data'];job=UUID(data['job_id'])
            export=db.execute('SELECT new_export_id FROM plm.aud_export_retry_generations WHERE new_job_id=%s',(job,)).fetchone()[0]
            claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60)
            assert claim.job_id==job
            c=windows.http.atomic.worker.fixture.w.AuditExportCaptureCommand(export,job,claim.fencing_token,'publisher-real')
            v['worker'].capture(c);staged=v['worker'].render(c);v['worker'].publish(c,staged)
            done=get(data['status_url'],retryable=False)
            assert done.json()['data']['state']=='SUCCEEDED'
        finally:db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s",(command.project_id,))
    print('Windows retry matrix PASS: actual PROJECT/GLOBAL Document committed-file original Owner GET false and precise retry409; real third Attempt fixture nonTEMP false/409 vs completed-time inconsistency503, restored; creator IM/customer false and retry404/noncreator customer404; archived PM new generation actual Worker success. HTTP refusals twenty tables unchanged. Technical fixture classification is not permanent Worker outcome; positive License/trust synthetic, no Parser/production/Gate/package proof.')

def observe(v,service,command,first,key):
    windows.observe(v,service,command,first,key,observe_client=matrix)

if __name__=='__main__':
    windows.http.atomic.worker.fixture.main(exercise=lambda v:windows.http.atomic.worker.exercise(v,
        observe_failed=lambda v,a,c:windows.http.atomic.observe(v,a,c,observe_http=observe)))
