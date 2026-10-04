"""Real durable sources/physical shapes; simulated interruption, reconstructed Owner.

No OS process kill or production recovery proof. Runs publication regression too.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os, time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_recover import AuditExportWorkerRecover
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.document.application.audit_export_metadata import AuditRegisteredFileRequest, AuditFileMetadataError
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor

load=spec_from_file_location('_recovery_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
f=module_from_spec(load);load.loader.exec_module(f)


def exercise(v):
    worker, storage, actual, prepare, db = (v[k] for k in ('worker','storage','actual','prepare','db'))
    runtime, users, root, leases = (v[k] for k in ('runtime','users','file_root','leases'))
    tables=('aud_exports','aud_export_acceptances','aud_export_captures','aud_export_members','aud_export_render_attempts','aud_export_results','aud_events','doc_file_objects','doc_file_state_events','job_jobs','job_leases','job_attempts','job_outbox_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def restarted():
        return AuditExportWorkerRecover(files=v['files'],results=v['results'],completion=v['completion'],audit=v['audit'],
            system_actor=create_windows_system_actor(resolver=v['SourceMapping']()),**v['deps'])
    def paths(staged):
        stage,final=f.f._locators(staged.content.coordinate)
        return root/stage,root/final
    def denied(service,c,code):
        before=snapshot()
        try:service.recover(c)
        except AuditExportWorkerError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('invalid recovery/replay accepted')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        for mode in ('stage','final','linked'):
            accepted,c,staged=prepare(scope,0 if mode=='stage' else 3)
            original_promote=storage.promote
            if mode=='final':
                original_completion=worker._completion
                class FailAfterCompletion:
                    def complete_current(self,*args,**kwargs):
                        original_completion.complete_current(*args,**kwargs)
                        raise RuntimeError('synthetic interrupted final transaction')
                worker._completion=FailAfterCompletion()
            else:
                def interrupt(content,*,mode='new'):
                    if test_mode=='linked':
                        stage,final=paths(staged);final.parent.mkdir(parents=True,exist_ok=True);os.link(stage,final)
                    raise RuntimeError('synthetic promotion interruption')
                test_mode=mode;storage.promote=interrupt
            try:
                worker.publish(c,staged)
            except AuditExportWorkerError:pass
            else:raise AssertionError('interruption succeeded')
            if mode=='final':worker._completion=original_completion
            else:storage.promote=original_promote
            assert actual.inspect(staged.content)=={'stage':'STAGE_ONLY','final':'FINAL_VERIFIED','linked':'LINKED_PAIR'}[mode]
            assert not db.execute('SELECT 1 FROM plm.aud_export_results WHERE export_id=%s',(c.export_id,)).fetchone()
            # The new service receives only command, not staged/Hash/manifest from this process.
            recovery=restarted();result=recovery.recover(c)
            assert result.file_id==staged.context.plan.file_id and result.file_sha256==staged.content.sha256
            assert actual.inspect(staged.content)=='FINAL_VERIFIED'
            before=snapshot()
            assert restarted().recover(c)==result and snapshot()==before
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses=list(pool.map(lambda _:restarted().recover(c),range(2)))
            assert responses==[result,result] and snapshot()==before
            # Registered source refuses unrelated scope/owner/actor/trace, without writes.
            coordinate=staged.content.coordinate
            request=AuditRegisteredFileRequest(accepted.intent.export_id,accepted.intent.actor_id,accepted.intent.trace_id,coordinate)
            with runtime.unit_of_work() as tx:
                assert v['files'].read_registered(tx,request=request).content==staged.content
            from uuid import uuid4
            for changes in (dict(export_id=uuid4()),dict(actor_id=uuid4()),dict(trace_id=uuid4()),
                            dict(coordinate=replace(coordinate,scope='PROJECT' if scope=='DEPLOYMENT' else 'DEPLOYMENT',project_id=v['project'] if scope=='DEPLOYMENT' else None))):
                try:
                    with runtime.unit_of_work() as tx:v['files'].read_registered(tx,request=replace(request,**changes))
                except AuditFileMetadataError:pass
                else:raise AssertionError('wrong registered source read')
            assert snapshot()==before
            if scope=='PROJECT' and mode=='final':
                db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                denied(recovery,c,'AUTH_ACCESS_DENIED')
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
            if mode=='linked':
                stage,final=paths(staged);data=final.read_bytes()
                final.write_bytes(data+b'corrupt')
                denied(recovery,c,'AUDIT_EXPORT_CONTENT_UNAVAILABLE')
                final.write_bytes(data);assert recovery.recover(c)==result
    # No registration: recovery cannot manufacture Hash/metadata or a successful result.
    accepted,c,staged=prepare();before=snapshot()
    denied(restarted(),c,'AUDIT_UNAVAILABLE');assert snapshot()==before
    # Partial registered file is NOT complete merely because its name is known.
    accepted,c,staged=prepare()
    identity=worker._identity();worker._run(c,lambda cmd:worker._register(cmd,staged,identity))
    stage,final=paths(staged);data=stage.read_bytes();stage.write_bytes(data[:-1])
    denied(restarted(),c,'AUDIT_EXPORT_CONTENT_UNAVAILABLE');assert not final.exists()
    # Cancellation after an interrupted private final remains authoritative.
    accepted,c,staged=prepare();identity=worker._identity()
    worker._run(c,lambda cmd:worker._register(cmd,staged,identity));actual.promote(staged.content)
    target=f.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),f.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with runtime.unit_of_work() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=users[0],reason='Synthetic interrupted recovery cancel');tx.commit()
    denied(restarted(),c,'STALE_LEASE')
    # Real commit followed by simulated lost acknowledgement: do not re-finish.
    accepted,c,staged=prepare();real_uow=worker._uow;real_completion=worker._completion;finished=[False]
    class ObservedCompletion:
        def complete_current(self,*args,**kwargs):
            value=real_completion.complete_current(*args,**kwargs);finished[0]=True;return value
    @contextmanager
    def lost_ack_uow():
        with real_uow() as tx:
            class Transaction:
                def __getattr__(self,name):return getattr(tx,name)
                def commit(self):
                    tx.commit()
                    if finished[0]:raise RuntimeError('synthetic lost commit acknowledgement')
            yield Transaction()
    worker._completion=ObservedCompletion();worker._uow=lost_ack_uow
    try:worker.publish(c,staged)
    except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
    else:raise AssertionError('lost acknowledgement not injected')
    finally:worker._completion=real_completion;worker._uow=real_uow
    assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('SUCCEEDED',)
    before=snapshot();original=restarted().recover(c)
    assert original.file_id==staged.context.plan.file_id and snapshot()==before
    # Expired previous generation cannot publish; takeover creates a distinct new file.
    accepted,c,staged=prepare(seconds=1)
    identity=worker._identity();worker._run(c,lambda cmd:worker._register(cmd,staged,identity))
    actual.promote(staged.content);old_file=paths(staged)[1];old_bytes=old_file.read_bytes()
    time.sleep(1.1);denied(restarted(),c,'STALE_LEASE')
    claim=leases.claim_next(worker_ref='recovery-next',lease_seconds=60);assert claim.job_id==c.job_id
    new_command=replace(c,fencing_token=claim.fencing_token,worker_ref='recovery-next')
    denied(restarted(),new_command,'AUDIT_UNAVAILABLE')
    new_staged=worker.render(new_command);assert new_staged.context.plan.file_id!=staged.context.plan.file_id
    result=worker.publish(new_command,new_staged)
    assert result.export_id==c.export_id and old_file.read_bytes()==old_bytes
    print('P03-A04-P04 PASS: real registered-source reconstruction with fresh Owner/command only; dualScope stage/final/actual linked recovery, true completed Job/Lease/Attempt and AVAILABLE/result sources, concurrent success replay no DB writes, wrong owner/actor/trace/Scope and revoked current User reject; corrupt published/partial/missing registered source fail closed; cancel/expired old generation rejected, takeover independent file with original fixed capture/old final retained; actual successful commit with simulated lost acknowledgement returns original result without writes. Interruption simulated, not OS process-kill; License synthetic, actual temporary Vault; HTTP/download/heartbeat/production account/three-platform recovery/release not proven.')


if __name__=='__main__':f.main(exercise=exercise)
