"""Actual accepted/captured immutable source -> safe bytes; memory sink, not Artifact."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import hashlib
import io
import json
from psycopg import sql
from sqlalchemy import event
from plm_assistant.modules.audit.application.export_contract import AuditExportAuthorityRequest
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer,AuditExportRenderError
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef

load=spec_from_file_location("_render_fixture",Path(__file__).resolve().parents[1]/"aud-03-a06-a03-worker-capture"/"verify.py")
w=module_from_spec(load);load.loader.exec_module(w);a=w.a;f=w.f


def main():
    name,runtime="auditrender_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=a.URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            a.command.upgrade(a.create_migration_config(url),"head");runtime=a.create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(2)]
                users=[f.auth.user(db,f"Synthetic renderer {i}",token,"DEPLOYMENT_ADMIN" if i else "NONE") for i,token in enumerate(tokens)]
                project=f.schema.insert(db,"prj_projects",dict(project_code="RENDER",project_code_normalized="render",name="Synthetic renderer",created_by=users[0]),"project_id")
                dept=f.schema.insert(db,"prj_departments",dict(project_id=project,department_code="D",department_code_normalized="d",name="Synthetic renderer department"),"department_id")
                f.schema.insert(db,"prj_project_members",dict(project_id=project,user_id=users[0],department_id=dept,project_role="PROJECT_MANAGER"),"project_member_id")
                guard=f.auth.Guard();projects=a.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=a.SqlAlchemyProjectAuthorizationRepository())
                repo=a.SqlAlchemyAuditExportSubmitRepository();queue=a.AuditExportJobQueue(a.SqlAlchemyAuditExportJobQueueRepository());audit=a.AuditService(a.SqlAlchemyAuditRepository())
                submit=a.AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=a.AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=projects,license_guard=guard),repository=repo,receipts=a.SqlAlchemyIdempotencyReceipts(),queue=queue,audit=audit)
                authority=w.AuditExportCurrentAuthority(users=w.SqlAlchemyCurrentUserAccess(),projects=projects,license_guard=guard)
                lease_repo=w.SqlAlchemyJobLeaseRepository();leases=w.JobLeaseService(unit_of_work=runtime.unit_of_work,repository=lease_repo)
                checkpoint=w.JobLeaseCheckpoint(repository=lease_repo);captures=w.SqlAlchemyAuditCaptureRepository()
                worker=w.AuditExportWorkerCapture(unit_of_work=runtime.unit_of_work,repository=repo,authority=authority,queue=queue,leases=checkpoint,captures=captures)
                renderer,source=AuditExportRenderer(),SqlAlchemyAuditExportRenderSource()
                now=datetime.now(timezone.utc)
                def append(scope):
                    with runtime.unit_of_work() as tx:
                        value=audit.append(tx,w.AuditEventDraft(trace_id=uuid4(),event_scope=scope,target_project_id=project if scope=="PROJECT" else None,actor_type="UNRESOLVED",actor_id=None,original_actor_id=None,actor_hint_digest=b'h'*32,action="SYNTHETIC_RENDER",outcome="DENIED"));tx.commit();return value
                ids={scope:append(scope) for scope in ("PROJECT","DEPLOYMENT")}
                def prepare(scope,action="SYNTHETIC_RENDER"):
                    spec=a.AuditExportSpec(scope,project if scope=="PROJECT" else None,"PROJECT_GOVERNANCE" if scope=="PROJECT" else "SECURITY_REVIEW",now-timedelta(hours=1),now+timedelta(hours=1),action=action)
                    accepted=submit.submit_idempotent(a.AuditExportSubmitAuthorizationRequest(tokens[0 if scope=="PROJECT" else 1],f.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
                    claim=leases.claim_next(worker_ref="renderer-worker",lease_seconds=60);assert claim.job_id==accepted.job_id
                    command=w.AuditExportCaptureCommand(accepted.intent.export_id,accepted.job_id,claim.fencing_token,"renderer-worker")
                    return accepted,command,worker.capture(command)
                def render(accepted,command,capture):
                    # Trusted fixture wiring, NOT a production rendering authorization service.
                    with runtime.unit_of_work() as tx:
                        intent=repo.peek_created(tx,export_id=accepted.intent.export_id)
                        request=AuditExportAuthorityRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,"RENDER")
                        authority.assert_current(tx,request=request)
                        assert repo.get_created(tx,export_id=intent.export_id)==intent
                        assert repo.get_accepted(tx,intent=intent)==accepted
                        assert queue.find_export(tx,request=submit._queue_request(intent))==AuditExportJobRef(accepted.job_id,accepted.event_id)
                        checkpoint.check_current(tx,job_id=command.job_id,fencing_token=command.fencing_token,worker_ref=command.worker_ref)
                        assert captures.read_capture(tx,request=request)==capture
                        sink=io.BytesIO();result=renderer.render(intent=intent,capture=capture,items=source.iter_events(tx,export_id=intent.export_id),sink=sink)
                        return result,sink.getvalue()
                tables=("aud_exports","aud_export_acceptances","aud_export_members","aud_export_captures","aud_events","job_jobs","job_leases","job_attempts","job_outbox_events","plt_idempotency_receipts")
                def snapshot():return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in tables}
                statements=[]
                def observe(conn,cursor,statement,parameters,context,executemany):
                    if "aud_export_members" in statement and "aud_events" in statement and "position" in statement:statements.append(statement)
                event.listen(runtime._engine,"before_cursor_execute",observe)
                try:
                    for scope in ("PROJECT","DEPLOYMENT"):
                        accepted,command,capture=prepare(scope);before=snapshot();result,blob=render(accepted,command,capture)
                        assert snapshot()==before and capture.member_count==1
                        body=json.loads(blob);assert body['audit_event_id']==str(ids[scope]) and body['event_scope']==scope
                        assert body['actor_type']=='UNRESOLVED' and body['actor_id'] is None
                        assert b'actor_hint_digest' not in blob and b'h'*32 not in blob and b'worker_ref' not in result.manifest_bytes
                        assert result.file_sha256==hashlib.sha256(blob).hexdigest() and result.byte_count==len(blob)
                        manifest=json.loads(result.manifest_bytes);assert manifest['membership_sha256']==capture.membership_hash
                        append(scope);assert render(accepted,command,capture)==(result,blob)
                        # Source of the other seal cannot silently render under this intent.
                        with runtime.unit_of_work() as tx:
                            try:renderer.render(intent=accepted.intent,capture=capture,items=(),sink=io.BytesIO())
                            except AuditExportRenderError:pass
                            else:raise AssertionError("missing fixed source rendered successfully")
                    accepted,command,capture=prepare("PROJECT","SYNTHETIC_EMPTY")
                    result,blob=render(accepted,command,capture);assert blob==b'' and result.member_count==0
                finally:event.remove(runtime._engine,"before_cursor_execute",observe)
                assert statements and all("actor_hint_digest" not in statement for statement in statements)
            print("AUD-03-A06-A04-P01 PASS: actual accepted/captured membership -> canonical safe JSONL/manifest memory bytes in both Scopes; exact file/hash/count/empty/new-event exclusion; no hint/path/Worker projection, explicit SQL columns and database no-write. Caller authority fixture, NOT production render UOW/storage/Artifact/publish/download/performance; License synthetic")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
