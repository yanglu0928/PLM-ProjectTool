"""Read-only actual Windows/schema precondition evidence; no public retry implementation."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest

spec=spec_from_file_location('_retry_precheck_windows',Path(__file__).resolve().parents[1]/'job-01-a05-p05-windows'/'verify.py')
windows=module_from_spec(spec);spec.loader.exec_module(windows)

def runtime(v, client, snapshot):
    db=v['db']; before=snapshot()
    for scope,pid,token in (('PROJECT',v['project'],v['tokens'][0]),('DEPLOYMENT',None,v['tokens'][1])):
        job=db.execute("SELECT job_id FROM plm.job_jobs WHERE owner_module='audit' AND state='SUCCEEDED' AND scope=%s ORDER BY job_id LIMIT 1",(scope,)).fetchone()[0]
        path=f'/api/v1/projects/{pid}/jobs/{job}' if pid else f'/api/v1/admin/jobs/{job}'
        detail=client.get(path,headers={'cookie':'plm_session='+token.hex()})
        assert detail.status_code==200 and detail.json()['data']['retryable'] is False
        # Existing GET /jobs/{job_id} matches this segment; absent POST reports 405.
        assert client.post(path+':retry',headers={'cookie':'plm_session='+token.hex(),'Idempotency-Key':str(uuid4()),'If-Match':detail.headers['etag']}).status_code==405
        with v['runtime'].unit_of_work() as tx:
            intent=v['repo'].get_created_for_job(tx,job_id=job)
            accepted=v['repo'].get_accepted(tx,intent=intent)
            refs=v['queue'].enqueue_export(tx,request=AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version))
            assert refs.job_id==job and refs.event_id==accepted.event_id
        assert snapshot()==before
    columns={r[0] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name='job_jobs'")}
    assert not columns.intersection({'source_job_id','original_job_id','retry_generation','parent_job_id'})
    assert db.execute("SELECT to_regclass('plm.aud_export_retry_generations')").fetchone()[0] is None
    assert snapshot()==before
    print('Retry precondition evidence PASS: real two Windows factories current successful Job retryable false/public retry405 GET-only path, original owned enqueue returns same immutable Job+event without writes; schema no dedicated generation lineage. User retry NOT implemented; automatic RUNNING Lease retry is not terminal user retry. CR-JOB-006 before new schema/owner command; no customer/production change.')

if __name__=='__main__':
    windows.mixed.fixture.main(exercise=lambda v:windows.mixed.exercise(v,observe_runtime=lambda v:windows.observe(v,observe_client=runtime)))
