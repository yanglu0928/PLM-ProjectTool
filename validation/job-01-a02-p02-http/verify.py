"""Reuse actual PG authorization matrix through optional ASGI Job GET."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.jobs.application.authorized_read import JobReadError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_http_job_fixture',ROOT/'validation/job-01-a01-read/verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)

def exercise(v):
    actual_constructor=p.AuthorizedJobReadService
    clients=[];proxies=[];counts={'accepted':0,'refused':0}
    class ThroughHttp:
        def __init__(self,actual):
            self.actual=actual
            router=create_job_detail_router(reads=actual,origins=LoginOriginPolicy(['https://plm.example.test']))
            self.client=TestClient(create_app(job_detail_router=router),base_url='https://plm.example.test')
            clients.append(self.client);proxies.append(self)
        def get(self,q):
            self.last=q
            path=f'/api/v1/projects/{q.project_id}/jobs/{q.job_id}' if q.project_id else f'/api/v1/admin/jobs/{q.job_id}'
            response=self.client.get(path,headers={'cookie':'plm_session='+q.session_token.hex()})
            try:value=self.actual.get(q)
            except JobReadError as exc:
                expected={'AUTH_ACCESS_DENIED':401,'RESOURCE_NOT_FOUND':404,'LICENSE_OPERATION_DENIED':403,'VALIDATION_FAILED':422}.get(exc.code,503)
                assert response.status_code==expected
                assert set(response.json())=={'error','trace_id'}
                counts['refused']+=1
                raise
            assert response.status_code==200
            data=response.json()['data']
            assert data['job_id']==str(q.job_id) and data['state']==value.facts.state
            assert data['scope']==value.facts.scope and data['attempt_count']==value.facts.attempt_count
            assert response.headers['etag']==data['etag']==f'"v{value.facts.lock_version}"'
            assert response.headers['cache-control']=='no-store'
            assert data['result_ref']==({'type':value.owner.result_type,'id':str(value.owner.result_id)} if value.owner.result_id else None)
            assert not any(x in data for x in ('actor_id','payload_refs','lease_expires_at','fencing_token','worker_ref','idempotency_key'))
            counts['accepted']+=1
            return value
    def constructor(**kwargs):return ThroughHttp(actual_constructor(**kwargs))
    p.AuthorizedJobReadService=constructor
    try:
        p.exercise(v)
        proxy=proxies[0];q=proxy.last;path=f'/api/v1/admin/jobs/{q.job_id}'
        with TestClient(create_app()) as default:assert default.get(path).status_code==404
        headers={'cookie':'plm_session='+q.session_token.hex()}
        assert proxy.client.get(path+'?scope=PROJECT',headers=headers).status_code==400
        assert proxy.client.get(path,headers=dict(headers,host='evil.test')).status_code==403
        response=proxy.client.get(path,headers=dict(headers,**{'if-none-match':'"v2"'}))
        assert response.status_code==200
        original=v['db'].execute('SELECT state FROM plm.auth_users WHERE user_id=%s',(v['users'][1],)).fetchone()[0]
        try:
            v['db'].execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(v['users'][1],))
            assert proxy.client.get(path,headers=dict(headers,**{'if-none-match':'"v2"'})).status_code==401
        finally:v['db'].execute('UPDATE plm.auth_users SET state=%s WHERE user_id=%s',(original,v['users'][1]))
        assert counts=={'accepted':8,'refused':13},counts
        print(f'JOB GET HTTP INTERNAL PASS: actual PG/Session/Project/Audit Owner matrix through ASGI, {counts}; real state/version/result refs/no-store, default404, bad query/Host and conditional never bypass revocation. Six business tables unchanged by matrix reads. Synthetic License, no Windows production composition/other Owner/browser/If-Match/package proof.')
    finally:
        p.AuthorizedJobReadService=actual_constructor
        for client in clients:client.close()

if __name__=='__main__':p.fixture.main(exercise=exercise)
