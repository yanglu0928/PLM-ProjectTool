"""Actual file + caller-UOW metadata/Audit; Export authority and Lease not supplied."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import hashlib
import tempfile
from uuid import uuid4
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate,AuditFileContent
from plm_assistant.modules.document.application.audit_export_metadata import RegisterAuditFile,AuditFileMetadataError
from plm_assistant.modules.document.infrastructure.audit_export_storage import LocalAuditExportFileStorage,_locators
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata
from plm_assistant.modules.audit.application.public import AuditService,AuditEventDraft
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository

load=spec_from_file_location("_audit_file_metadata_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="auditfilemeta_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-audit-meta-") as temp:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            storage=LocalAuditExportFileStorage(LocalFileStorage(Path(temp).resolve()))
            metadata=SqlAlchemyAuditExportFileMetadata();audit=AuditService(SqlAlchemyAuditRepository())
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic audit file metadata",b"m"*32,"DEPLOYMENT_ADMIN")
                other=f.auth.user(db,"Synthetic other audit metadata",b"o"*32,"NONE")
                project=f.schema.insert(db,"prj_projects",dict(project_code="META",project_code_normalized="meta",name="Synthetic Metadata",created_by=actor),"project_id")
                def prepare(scope="DEPLOYMENT",data='{"synthetic":"中文"}\n'.encode('utf-8')):
                    coordinate=AuditFileCoordinate(uuid4(),scope,project if scope=="PROJECT" else None)
                    with storage.staging_sink(coordinate) as sink:sink.write(data)
                    content=AuditFileContent(coordinate,hashlib.sha256(data).digest(),len(data))
                    storage.verify_staged(content)
                    return RegisterAuditFile(uuid4(),actor,uuid4(),content)
                def append(tx,request,state):
                    return audit.append(tx,AuditEventDraft(trace_id=request.trace_id,event_scope=request.content.coordinate.scope,
                        target_project_id=request.content.coordinate.project_id,actor_type="USER",actor_id=actor,
                        original_actor_id=None,actor_hint_digest=None,action="SYNTHETIC_AUDIT_FILE_"+state,outcome="SUCCESS",
                        target_owner_module="document",target_object_type="DOC-03",target_object_id=request.content.coordinate.file_id))
                def register(request):
                    with runtime.unit_of_work() as tx:
                        result=metadata.register_staged(tx,request=request)
                        if result.changed:append(tx,request,"REGISTER")
                        tx.commit();return result
                def available(request):
                    with runtime.unit_of_work() as tx:
                        result=metadata.mark_available(tx,request=request,expected_version=0)
                        if result.changed:append(tx,request,"PUBLISH")
                        tx.commit();return result
                def counts():return tuple(db.execute("SELECT (SELECT count(*) FROM plm.doc_file_objects),(SELECT count(*) FROM plm.doc_file_state_events),(SELECT count(*) FROM plm.aud_events)").fetchone())
                def denied(call,code="FILE_UNAVAILABLE"):
                    try:
                        with runtime.unit_of_work() as tx:call(tx)
                    except AuditFileMetadataError as exc:assert exc.code==code,exc.code;return
                    raise AssertionError("invalid or stale metadata accepted")
                requests=[]
                for scope in ("DEPLOYMENT","PROJECT"):
                    request=prepare(scope);requests.append(request)
                    first=register(request);assert first.changed and first.metadata.state=="STAGED"
                    before=counts();replay=register(replace(request,trace_id=uuid4()))
                    assert not replay.changed and replay.metadata==first.metadata and counts()==before
                    storage.promote(request.content)
                    published=available(request);assert published.changed and published.metadata.state=="AVAILABLE"
                    before=counts();again=available(replace(request,trace_id=uuid4()))
                    assert not again.changed and again.metadata==published.metadata and counts()==before
                    with runtime.unit_of_work() as tx:assert metadata.get(tx,request=request)==published.metadata
                    for changed in (replace(request,export_id=uuid4()),replace(request,actor_id=other),
                        replace(request,content=replace(request.content,sha256=b"x"*32)),
                        replace(request,content=replace(request.content,size_bytes=0)),
                        replace(request,content=replace(request.content,coordinate=replace(request.content.coordinate,
                            scope="PROJECT" if scope=="DEPLOYMENT" else "DEPLOYMENT",project_id=project if scope=="DEPLOYMENT" else None)))):
                        denied(lambda tx,changed=changed:metadata.get(tx,request=changed))
                        denied(lambda tx,changed=changed:metadata.register_staged(tx,request=changed))
                    denied(lambda tx:metadata.mark_available(tx,request=request,expected_version=True),"CONFLICT_VERSION")
                    db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED',lock_version=2 WHERE file_object_id=%s",(request.content.coordinate.file_id,))
                    denied(lambda tx:metadata.mark_available(tx,request=request,expected_version=0),"CONFLICT_STATE")
                # Actual concurrent first registration and publication, no duplicate provenance/Audit.
                request=prepare(data=b"")
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(register,(request,replace(request,trace_id=uuid4()))))
                assert sum(r.changed for r in results)==1 and results[0].metadata==results[1].metadata
                with runtime.unit_of_work() as tx:
                    observed=metadata.get(tx,request=request)
                    def competing_lock():
                        with f.schema.connect(name) as rival:
                            rival.execute("SET lock_timeout='100ms'")
                            try:
                                with rival.transaction():rival.execute("SELECT file_object_id FROM plm.doc_file_objects WHERE file_object_id=%s FOR UPDATE",(request.content.coordinate.file_id,))
                            except psycopg.errors.LockNotAvailable:return True
                            return False
                    with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competing_lock).result()
                    assert observed.state=="STAGED"
                storage.promote(request.content)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(available,(request,replace(request,trace_id=uuid4()))))
                assert sum(r.changed for r in results)==1 and results[0].metadata==results[1].metadata
                # Registration and publication failures roll back all DB effects; bytes are not rolled back.
                request=prepare();before=counts()
                try:
                    with runtime.unit_of_work() as tx:
                        metadata.register_staged(tx,request=request);append(tx,request,"REGISTER")
                        raise RuntimeError("synthetic caller failure after Audit")
                except RuntimeError:pass
                assert counts()==before
                register(request);storage.promote(request.content);before=counts()
                try:
                    with runtime.unit_of_work() as tx:
                        metadata.mark_available(tx,request=request,expected_version=0);append(tx,request,"PUBLISH")
                        raise RuntimeError("synthetic caller failure after Audit")
                except RuntimeError:pass
                assert counts()==before
                with runtime.unit_of_work() as tx:assert metadata.get(tx,request=request).state=="STAGED"
                assert storage.inspect(request.content)=="FINAL_VERIFIED"
                available(request)
                # A plausible manual row is NOT provenance, and ordinary usage cannot be rebound.
                request=prepare();_,final=_locators(request.content.coordinate)
                f.schema.insert(db,"doc_file_objects",dict(file_object_id=request.content.coordinate.file_id,scope="DEPLOYMENT",
                    usage_kind="AUDIT_EXPORT",owner_object_id=request.export_id,storage_class="PERSISTENT",storage_locator=final,
                    original_name_metadata="audit-export.jsonl",sha256=request.content.sha256,size_bytes=request.content.size_bytes,
                    detected_mime="application/x-ndjson",created_by=actor),"file_object_id")
                denied(lambda tx:metadata.register_staged(tx,request=request))
                request=prepare("PROJECT")
                f.schema.insert(db,"doc_file_objects",dict(file_object_id=request.content.coordinate.file_id,scope="PROJECT",project_id=project,
                    storage_class="PERSISTENT",storage_locator="projects/synthetic-ordinary",original_name_metadata="ordinary",created_by=actor),"file_object_id")
                denied(lambda tx:metadata.register_staged(tx,request=request))
            print("P03-A02-P02 PASS: actual files + caller-UOW owned metadata/state events/real Audit in both Scopes; original trace/replay/concurrent single registration and AVAILABLE event; exact identity/content/usage/no-provenance refusals, restricted no revive; post-Audit fault full DB rollback with final file remaining private. Synthetic Export IDs/trusted caller, NOT actual authority/Lease/atomic Job-result publication or HTTP.")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
