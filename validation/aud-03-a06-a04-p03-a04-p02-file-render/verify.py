"""Real accepted Worker/current auth/lease/source -> actual private staging outside UOW."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
import hashlib,json,time,os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from unittest.mock import patch
from psycopg import sql
from plm_assistant.modules.audit.application.worker_render import AuditExportWorkerRender
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource
from plm_assistant.modules.document.infrastructure.audit_export_storage import LocalAuditExportFileStorage,_locators
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage

load=spec_from_file_location('_file_render_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a03-p02-worker-plan'/'verify.py')
p=module_from_spec(load);load.loader.exec_module(p);w,a,f=p.w,p.a,p.f


def main():
    name,runtime='filerender_'+uuid4().hex[:12],None
    with f.schema.connect('postgres') as admin,TemporaryDirectory(prefix='PLM-中文渲染-') as folder:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url=a.URL.create('postgresql+psycopg',username='poc_admin',host='127.0.0.1',port=55432,database=name)
            a.command.upgrade(a.create_migration_config(url),'head');runtime=a.create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(2)]
                users=[f.auth.user(db,f'Synthetic file render {i}',token,'DEPLOYMENT_ADMIN' if i else 'NONE') for i,token in enumerate(tokens)]
                project=f.schema.insert(db,'prj_projects',dict(project_code='FR',project_code_normalized='fr',name='Synthetic file rendering',created_by=users[0]),'project_id')
                dept=f.schema.insert(db,'prj_departments',dict(project_id=project,department_code='D',department_code_normalized='d',name='Synthetic render department'),'department_id')
                f.schema.insert(db,'prj_project_members',dict(project_id=project,user_id=users[0],department_id=dept,project_role='PROJECT_MANAGER'),'project_member_id')
                projects=a.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=a.SqlAlchemyProjectAuthorizationRepository())
                guard=f.auth.Guard();repo=a.SqlAlchemyAuditExportSubmitRepository();queue=a.AuditExportJobQueue(a.SqlAlchemyAuditExportJobQueueRepository());audit=a.AuditService(a.SqlAlchemyAuditRepository())
                submit=a.AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=a.AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=projects,license_guard=guard),repository=repo,receipts=a.SqlAlchemyIdempotencyReceipts(),queue=queue,audit=audit)
                lease_repo=w.SqlAlchemyJobLeaseRepository();leases=w.JobLeaseService(unit_of_work=runtime.unit_of_work,repository=lease_repo)
                active=[0];writes=[0];pages=[]
                @contextmanager
                def tracked_uow():
                    with runtime.unit_of_work() as tx:
                        active[0]+=1
                        try:yield tx
                        finally:active[0]-=1
                deps=dict(unit_of_work=tracked_uow,repository=repo,authority=w.AuditExportCurrentAuthority(users=w.SqlAlchemyCurrentUserAccess(),projects=projects,license_guard=guard),queue=queue,leases=w.JobLeaseCheckpoint(repository=lease_repo),captures=w.SqlAlchemyAuditCaptureRepository(),plans=p.SqlAlchemyAuditRenderPlans())
                actual_storage=LocalAuditExportFileStorage(LocalFileStorage(Path(folder).resolve()))
                class TrackedStorage:
                    on_write=None;on_verify=None;write_failure=None
                    @contextmanager
                    def staging_sink(self,coordinate):
                        assert active[0]==0
                        original_fsync=os.fsync
                        def checked_fsync(fd):assert active[0]==0;return original_fsync(fd)
                        with patch('plm_assistant.modules.document.infrastructure.audit_export_storage.os.fsync',side_effect=checked_fsync),actual_storage.staging_sink(coordinate) as sink:
                            owner=self
                            class Sink:
                                def write(self,data):
                                    assert active[0]==0;writes[0]+=1
                                    if owner.write_failure and writes[0]==129:raise OSError('synthetic ENOSPC detail')
                                    count=sink.write(data)
                                    if owner.on_write and writes[0]==128:owner.on_write()
                                    return count
                            yield Sink()
                        assert active[0]==0
                    def verify_staged(self,expected):
                        assert active[0]==0
                        proof=actual_storage.verify_staged(expected)
                        if self.on_verify:self.on_verify()
                        return proof
                storage=TrackedStorage()
                class Source(SqlAlchemyAuditExportRenderSource):
                    fail=False;short=False
                    def read_page(self,tx,**kwargs):
                        assert active[0]==1;pages.append(kwargs['after_position'])
                        value=super().read_page(tx,**kwargs)
                        if self.fail and kwargs['after_position']==128:raise RuntimeError('synthetic source failure')
                        if self.short and kwargs['after_position']==128:return value[:-1]
                        return value
                source=Source();worker=AuditExportWorkerRender(source=source,storage=storage,**deps)
                def prepare(scope='PROJECT',count=260,seconds=60):
                    now=datetime.now(timezone.utc);trace=uuid4()
                    actor=users[0 if scope=='PROJECT' else 1]
                    spec=a.AuditExportSpec(scope,project if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now+timedelta(hours=1),action='SYNTHETIC_RENDER',trace_id=trace)
                    accepted=submit.submit_idempotent(a.AuditExportSubmitAuthorizationRequest(tokens[0 if scope=='PROJECT' else 1],f.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
                    with runtime.unit_of_work() as tx:
                        for _ in range(count):audit.append(tx,w.AuditEventDraft(trace_id=trace,event_scope=scope,target_project_id=spec.project_id,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,action='SYNTHETIC_RENDER',outcome='SUCCESS'))
                        tx.commit()
                    claim=leases.claim_next(worker_ref='worker-real',lease_seconds=seconds);assert claim.job_id==accepted.job_id
                    c=w.AuditExportCaptureCommand(accepted.intent.export_id,accepted.job_id,claim.fencing_token,'worker-real')
                    worker.capture(c);return accepted,c
                def private_file(c):
                    row=db.execute('SELECT file_id FROM plm.aud_export_render_attempts WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()
                    assert row
                    files=list(Path(folder).rglob(row[0].hex));assert len(files)==1
                    return files[0]
                def no_publish(c):
                    assert db.execute('SELECT count(*) FROM plm.doc_file_objects').fetchone()==(0,)
                    assert db.execute('SELECT count(*) FROM plm.aud_export_results').fetchone()==(0,)
                    assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()[0]!='SUCCEEDED'
                    if (Path(folder)/'generated').exists():assert not list((Path(folder)/'generated').rglob('*'))
                def reset():writes[0]=0;pages.clear();storage.on_write=storage.on_verify=storage.write_failure=None;source.fail=source.short=False
                def deny(c,code):
                    try:worker.render(c)
                    except w.AuditExportWorkerError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError('invalid file rendering accepted')
                    no_publish(c);assert active[0]==0
                for scope in ('PROJECT','DEPLOYMENT'):
                    for count in (0,260):
                        reset();accepted,c=prepare(scope,count)
                        # Real matching late source must not alter original fixed membership.
                        with runtime.unit_of_work() as tx:
                            audit.append(tx,w.AuditEventDraft(trace_id=accepted.intent.spec.trace_id,event_scope=scope,target_project_id=accepted.intent.spec.project_id,actor_type='USER',actor_id=accepted.intent.actor_id,original_actor_id=None,actor_hint_digest=None,action='SYNTHETIC_RENDER',outcome='SUCCESS'));tx.commit()
                        result=worker.render(c);result.__post_init__();path=private_file(c);blob=path.read_bytes()
                        assert len(blob.splitlines())==count and len(blob)==result.rendered.byte_count
                        assert hashlib.sha256(blob).digest()==result.content.sha256
                        assert json.loads(result.rendered.manifest_bytes)['member_count']==count
                        assert pages==([0,128,256] if count else []) and writes[0]==count
                        assert actual_storage.inspect(result.content)=='STAGE_ONLY'
                        assert b'actor_hint_digest' not in blob and not hasattr(result.content,'locator')
                        no_publish(c);original=blob;deny(c,'AUDIT_EXPORT_RENDER_FAILED');assert path.read_bytes()==original
                # Page boundary mutation is performed outside locks/UOW and next page rejects.
                reset();accepted,c=prepare();storage.on_write=lambda:db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(c,'AUTH_ACCESS_DENIED');assert len(private_file(c).read_bytes().splitlines())==128
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                reset();accepted,c=prepare()
                canceller=w.AuditExportCancellation(repository=w.SqlAlchemyAuditExportCancellationRepository())
                def cancel_now():
                    assert active[0]==0
                    with runtime.unit_of_work() as tx:canceller.request_cancel(tx,target=w.AuditExportCancellationTarget(submit._queue_request(accepted.intent),w.AuditExportJobRef(accepted.job_id,accepted.event_id)),requested_by=users[0],reason='Synthetic page cancellation');tx.commit()
                storage.on_write=cancel_now;deny(c,'STALE_LEASE');assert len(private_file(c).read_bytes().splitlines())==128
                reset();accepted,c=prepare(seconds=1);storage.on_write=lambda:time.sleep(1.15)
                deny(c,'STALE_LEASE');old=private_file(c);oldbytes=old.read_bytes()
                nextclaim=leases.claim_next(worker_ref='next',lease_seconds=60);assert nextclaim.job_id==c.job_id
                reset();nextc=replace(c,fencing_token=nextclaim.fencing_token,worker_ref='next');result=worker.render(nextc)
                assert result.context.plan.file_id.hex!=old.name and old.read_bytes()==oldbytes
                assert len(private_file(nextc).read_bytes().splitlines())==260;no_publish(nextc)
                reset();accepted,c=prepare();source.fail=True;deny(c,'AUDIT_UNAVAILABLE');assert len(private_file(c).read_bytes().splitlines())==128
                reset();accepted,c=prepare();source.short=True;deny(c,'AUDIT_UNAVAILABLE')
                reset();accepted,c=prepare();storage.write_failure=True;deny(c,'AUDIT_EXPORT_RENDER_FAILED');assert len(private_file(c).read_bytes().splitlines())==128
                reset();accepted,c=prepare(count=1);storage.on_verify=lambda:setattr(guard,'enabled',False)
                deny(c,'LICENSE_OPERATION_DENIED');guard.enabled=True
                assert len(private_file(c).read_bytes().splitlines())==1
            print('P03-A04-P02 PASS: real submit/claim/fixed capture/current authority/Lease/plan -> actual bounded private file+fsync/hash, dualScope empty/260-row pages/fullmanifest/late-event exclusion/Chinese path; writes/verify no DB UOW; page revoke/actual cancel/expiry/source failure/short page/simulated write ENOSPC/final License deny never publish; new generation independent file/original partial retained. License synthetic; no metadata/result/Job success/promote/download/heartbeat/performance/production proof.')
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__=='__main__':main()
