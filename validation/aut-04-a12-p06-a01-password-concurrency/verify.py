"""Twenty concurrent actual Windows ASGI requests; never claims network performance."""
import asyncio
import json
import math
from collections import Counter
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from time import perf_counter
from uuid import UUID,uuid4
from unittest.mock import patch
import httpx
from sqlalchemy import event
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.auth.application.session_service import SessionError

ROOT=Path(__file__).resolve().parents[1]
spec=spec_from_file_location('_password_performance_windows',ROOT/'aut-04-a11-p05-windows-user-state'/'verify.py')
windows=module_from_spec(spec);spec.loader.exec_module(windows)
spec=spec_from_file_location('_password_performance_source',ROOT/'aut-04-a12-p05-a06-reset-http'/'verify.py')
http=module_from_spec(spec);spec.loader.exec_module(http);m=http.m
ORIGIN='https://plm.example.test'
OUTCOME=[]


async def batch(app,requests):
    start=asyncio.Event()
    async def one(method,path,headers,body):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN,timeout=30) as client:
            await start.wait();began=perf_counter()
            response=await client.request(method,path,headers=headers,json=body)
            elapsed=(perf_counter()-began)*1000
            return elapsed,response
    tasks=[asyncio.create_task(one(*request)) for request in requests]
    await asyncio.sleep(0);start.set()
    return await asyncio.gather(*tasks)


def extra(v,settings):
    hasher=m.ScryptPasswordHasher()
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=m.SqlAlchemyIdempotencyReceipts())
    def issue(uid,password):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password.encode())))
    def headers(session=None):return {'origin':ORIGIN,
        'cookie':'plm_session='+(v['tokens'][1] if session is None else session.token).hex(),
        'x-csrf-token':(m.fixture.base.auth.CSRF if session is None else session.csrf_token).hex(),
        'idempotency-key':str(uuid4())}
    old='Synthetic concurrency original';temporary='Synthetic concurrency temporary';normal='Synthetic concurrency normal'
    database_errors=[];real_runtime=prod.create_database_runtime
    def monitored_runtime(url):
        runtime=real_runtime(url)
        def on_error(context):
            database_errors.append({'sqlstate':getattr(context.original_exception,'sqlstate',None),
                'operation':'deployment_advisory_lock' if 'pg_advisory_xact_lock' in (context.statement or '') else 'other'})
        event.listen(runtime._engine,'handle_error',on_error)
        return runtime
    with patch('plm_assistant.entrypoints.production_login.create_database_runtime',side_effect=monitored_runtime):
        app=prod.create_production_platform_write_app(settings)
    observations=[]
    def measure(name,requests,limit):
        rows=asyncio.run(batch(app,requests));times=sorted(elapsed for elapsed,_ in rows)
        report={'group':name,'concurrency':20,'samples':len(rows),'statuses':dict(Counter(response.status_code for _,response in rows)),
            'min_ms':round(times[0],3),'median_ms':round(times[len(times)//2],3),
            'p95_ms':round(times[math.ceil(.95*len(times))-1],3),'max_ms':round(times[-1],3),'limit_ms':limit}
        report['functional_all_200']=all(response.status_code==200 for _,response in rows)
        report['performance_pass']=report['functional_all_200'] and times[math.ceil(.95*len(times))-1]<=limit
        observations.append(report)
        print('PASSWORD_CONCURRENCY '+json.dumps(report,sort_keys=True))
        assert all(response.status_code in (200,503) for _,response in rows),'Unexpected response; inspect safe aggregate report'
        return [response for _,response in rows]
    with TestClient(app,base_url=ORIGIN) as client:
        users=[];old_sessions=[]
        for i in range(20):
            response=client.post('/api/v1/admin/users',headers=headers(),json={'username':f'Synthetic concurrency user {i}','password':old})
            assert response.status_code==201,response.status_code
            uid=UUID(response.json()['data']['user_id'])
            users.append(uid);old_sessions.append(issue(uid,old))
        measure('session_get',[('GET','/api/v1/auth/session',headers(session),None) for session in old_sessions],500)
        resets=[('POST',f'/api/v1/admin/users/{uid}:reset-password',headers()|{'if-match':'"v1"'},
            {'temporary_password':temporary,'must_change_password':True}) for uid in users]
        firsts=measure('reset_fresh',resets,1000)
        assert all(response.status_code==200 for response in firsts),'Reset functional failure; aggregate retained'
        assert all(response.json()['data']=={'credential_version':2} and response.headers['etag']=='"v2"' for response in firsts)
        for old_session in old_sessions:
            try:sessions.validate(old_session.token)
            except SessionError as exc:assert exc.code=='AUTH_SESSION_EXPIRED'
            else:raise AssertionError('Old Session survived reset')
        restricted=[issue(uid,temporary) for uid in users]
        assert all(sessions.validate(session.token).credential_version==2 for session in restricted)
        changes=[('POST','/api/v1/auth/password:change',headers(session),{'current_password':temporary,'new_password':normal})
            for session in restricted]
        changed=measure('change_fresh',changes,1000)
        succeeded=0;rolled_back=0
        for uid,session,response in zip(users,restricted,changed,strict=True):
            root=v['db'].execute('SELECT credential_version,lock_version FROM plm.auth_users WHERE user_id=%s',(uid,)).fetchone()
            first_count=v['db'].execute('SELECT count(*) FROM plm.auth_password_change_results WHERE user_id=%s',(uid,)).fetchone()[0]
            if response.status_code==200:
                assert response.json()['data']=={'credential_version':3} and tuple(root)==(3,3) and first_count==1
                try:sessions.validate(session.token)
                except SessionError as exc:assert exc.code=='AUTH_SESSION_EXPIRED'
                else:raise AssertionError('Restricted Session survived change')
                assert sessions.validate(issue(uid,normal).token).credential_version==3
                succeeded+=1
            else:
                assert response.json()['error']['code']=='SYSTEM_UNAVAILABLE'
                assert tuple(root)==(2,2) and first_count==0
                assert sessions.validate(session.token).credential_version==2
                assert v['db'].execute('SELECT count(*) FROM plm.auth_password_credentials WHERE user_id=%s',(uid,)).fetchone()[0]==2
                assert v['db'].execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PASSWORD_CHANGED'",(uid,)).fetchone()[0]==0
                rolled_back+=1
        reset_rows=v['db'].execute('SELECT count(*) FROM plm.auth_password_reset_results WHERE user_id=ANY(%s)',(users,)).fetchone()[0]
        change_rows=v['db'].execute('SELECT count(*) FROM plm.auth_password_change_results WHERE user_id=ANY(%s)',(users,)).fetchone()[0]
        assert reset_rows==20 and change_rows==succeeded
        print('PASSWORD_CONCURRENCY_INTEGRITY '+json.dumps({'reset_firsts':reset_rows,'change_firsts':change_rows,
            'change_succeeded':succeeded,'failed_change_original_credential_and_session_retained':rolled_back},sort_keys=True))
        print('PASSWORD_CONCURRENCY_DATABASE_ERRORS '+json.dumps(database_errors,sort_keys=True))
    OUTCOME.append(all(row['performance_pass'] for row in observations))
    print('PASSWORD_CONCURRENCY_SUMMARY '+json.dumps({'functional_pass':all(row['functional_all_200'] for row in observations),
        'performance_pass':all(row['performance_pass'] for row in observations),'reports':observations,
        'scope':'Windows11 actual factory, PG18, real Scrypt, synthetic trust, ASGI in process; no network/TLS/production proof'},sort_keys=True))


if __name__=='__main__':
    windows.http.m.fixture.main(exercise=lambda v:windows.exercise(v,extra=extra))
    if OUTCOME!=[True]:raise SystemExit('PASSWORD_CONCURRENCY FAIL: retain original acceptance thresholds; see safe aggregate evidence')
