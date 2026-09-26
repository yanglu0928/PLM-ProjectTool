"""Actual disposable PostgreSQL FileObject usage migration, NOT file delivery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4, UUID
import psycopg
from psycopg import sql
from alembic import command, op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.document.application.change_file_state import ChangeFileState, FileStateCommandError
from plm_assistant.modules.document.application.publish_file import PublishFile, FilePublishError
from plm_assistant.modules.document.infrastructure.file_state_repository import SqlAlchemyFileStateRepository
from plm_assistant.modules.document.infrastructure.file_publish_repository import SqlAlchemyFilePublishRepository

spec = spec_from_file_location("_audit_file_schema_fixture", Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f = module_from_spec(spec); spec.loader.exec_module(f)


def main():
    name = "auditfiles_" + uuid4().hex[:12]
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head"); command.downgrade(cfg, "20260926_0039"); command.upgrade(cfg, "head")
            engine = create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs = compare_metadata(MigrationContext.configure(conn, opts={"include_schemas":True,
                        "include_object":lambda obj,name,type_,reflected,compare_to: name=="doc_file_objects" if type_=="table" else True}), Base.metadata)
                    assert not diffs, str(diffs)
            finally: engine.dispose()
            command.downgrade(cfg, "20260926_0039")
            with f.schema.connect(name) as db:
                actor = f.auth.user(db, "Synthetic Audit File Owner", b"f"*32, "DEPLOYMENT_ADMIN")
                project = f.schema.insert(db, "prj_projects", dict(project_code="AF",project_code_normalized="af",name="Synthetic File Project",created_by=actor), "project_id")
                def create_file(**changes):
                    values = dict(scope="PROJECT",project_id=project,storage_class="PERSISTENT",
                        storage_locator="projects/"+uuid4().hex,original_name_metadata="synthetic.jsonl",created_by=actor,
                        sha256=b"h"*32,size_bytes=0,detected_mime="application/x-ndjson")
                    values.update(changes)
                    return f.schema.insert(db, "doc_file_objects", values, "file_object_id")
                old_files = [create_file(), create_file(scope="GLOBAL",project_id=None)]
                document = f.schema.insert(db,"doc_documents",dict(scope="PROJECT",project_id=project,document_category="PROJECT_RECORD",title="Synthetic doc",original_display_name="synthetic.jsonl",created_by=actor),"document_id")
                def create_upload():
                    return f.schema.insert(db,"doc_upload_intents",dict(scope="PROJECT",project_id=project,actor_id=actor,
                        target_document_id=document,purpose_code="PROJECT_RECORD",original_display_name="synthetic.jsonl",token_digest=uuid4().bytes+uuid4().bytes,
                        expires_at=datetime.now(timezone.utc)+timedelta(hours=1)),"upload_id")
                upload = create_upload()
                global_doc=f.schema.insert(db,"doc_documents",dict(scope="GLOBAL",document_category="REFERENCE_MATERIAL",
                    title="Synthetic old global version",original_display_name="old.jsonl",created_by=actor),"document_id")
                db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',available_at=clock_timestamp(),lock_version=1 WHERE file_object_id=%s",(old_files[1],))
                old_version=f.schema.insert(db,"doc_document_versions",dict(document_id=global_doc,scope="GLOBAL",version_no=1,
                    file_object_id=old_files[1],content_sha256=b"h"*32,size_bytes=0,detected_mime="application/x-ndjson",created_by=actor),"document_version_id")
                retained={table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY {}").format(sql.Identifier(table),sql.Identifier(key))))
                    for table,key in (("doc_documents","document_id"),("doc_document_versions","document_version_id"),("doc_upload_intents","upload_id"))}
                def unchanged_refs():
                    for table,key in (("doc_documents","document_id"),("doc_document_versions","document_version_id"),("doc_upload_intents","upload_id")):
                        assert tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY {}").format(sql.Identifier(table),sql.Identifier(key))))==retained[table]
                columns = [row[0] for row in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name='doc_file_objects' ORDER BY ordinal_position")]
                old_query = sql.SQL("SELECT {} FROM plm.doc_file_objects ORDER BY file_object_id").format(sql.SQL(',').join(map(sql.Identifier,columns)))
                before = tuple(db.execute(old_query))
                command.upgrade(cfg,"head")
                unchanged_refs()
                assert tuple(db.execute(old_query))==before
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE usage_kind<>'DOCUMENT' OR owner_object_id IS NOT NULL").fetchone()==(0,)
                execute = op.execute
                def locked(statement,*args,**kwargs):
                    result=execute(statement,*args,**kwargs)
                    if str(statement).startswith("LOCK TABLE plm.doc_documents,"):
                        def competitor():
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='100ms'")
                                try:
                                    with rival.transaction(): rival.execute("LOCK TABLE plm.doc_file_objects IN ROW EXCLUSIVE MODE")
                                except psycopg.errors.LockNotAvailable: return True
                                return False
                        with ThreadPoolExecutor(max_workers=1) as pool: assert pool.submit(competitor).result()
                    return result
                with patch("alembic.op.execute",side_effect=locked): command.downgrade(cfg,"20260926_0039")
                unchanged_refs()
                assert tuple(db.execute(old_query))==before
                command.upgrade(cfg,"head")
                unchanged_refs()
                def denied(action, message=None):
                    try:
                        with db.transaction(): action()
                    except (psycopg.errors.CheckViolation,psycopg.errors.RaiseException,psycopg.errors.ForeignKeyViolation) as exc:
                        if message: assert message in str(exc), str(exc)
                        return
                    raise AssertionError("invalid audit file or destructive history write accepted")
                def audit_file(**changes):
                    values=dict(usage_kind="AUDIT_EXPORT",owner_object_id=uuid4());values.update(changes)
                    return create_file(**values)
                for changes in (dict(owner_object_id=None),dict(owner_object_id=UUID(int=0)),dict(scope="GLOBAL",project_id=None),
                    dict(scope="DEPLOYMENT",project_id=project),dict(scope="PROJECT",project_id=None),dict(storage_class="TEMPORARY"),
                    dict(sha256=None),dict(size_bytes=None),dict(size_bytes=134217729),dict(detected_mime="application/pdf"),
                    dict(file_state="AVAILABLE",available_at=datetime.now(timezone.utc)+timedelta(seconds=1)),dict(file_state="FAILED"),dict(lock_version=1),dict(created_at="infinity"),dict(sha256=b"short")):
                    denied(lambda changes=changes:audit_file(**changes))
                denied(lambda:create_file(scope="DEPLOYMENT",project_id=None))
                denied(lambda:create_file(owner_object_id=uuid4()))
                denied(lambda:db.execute("UPDATE plm.doc_file_objects SET usage_kind='AUDIT_EXPORT',owner_object_id=%s WHERE file_object_id=%s",(uuid4(),old_files[0])))
                audit = audit_file(); deployment = audit_file(scope="DEPLOYMENT",project_id=None)
                runtime=create_database_runtime(url)
                try:
                    with runtime.unit_of_work() as tx:
                        try: SqlAlchemyFileStateRepository().change(tx,command=ChangeFileState(audit,"PROJECT",project,actor,uuid4(),0,"FAILED","SYNTHETIC_FAILURE"))
                        except FileStateCommandError as exc: assert exc.code=="RESOURCE_NOT_FOUND"
                        else: raise AssertionError("ordinary file state handler accepted Audit usage")
                        try: SqlAlchemyFilePublishRepository().staged(tx,command=PublishFile(audit,"PROJECT",project,actor,uuid4(),0,134217728))
                        except FilePublishError as exc: assert exc.code=="RESOURCE_NOT_FOUND"
                        else: raise AssertionError("ordinary publish handler accepted Audit usage")
                finally: runtime.dispose()
                frozen=db.execute("SELECT * FROM plm.doc_file_objects WHERE file_object_id=%s",(audit,)).fetchone()
                for column,value in (("owner_object_id",uuid4()),("usage_kind","DOCUMENT"),("sha256",b"x"*32),
                    ("size_bytes",1),("storage_locator","projects/changed"),("scope","DEPLOYMENT"),("file_state","FAILED"),("lock_version",1)):
                    denied(lambda column=column,value=value:db.execute(sql.SQL("UPDATE plm.doc_file_objects SET {}=%s WHERE file_object_id=%s").format(sql.Identifier(column)),(value,audit)))
                assert db.execute("SELECT * FROM plm.doc_file_objects WHERE file_object_id=%s",(audit,)).fetchone()==frozen
                denied(lambda:db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=1 WHERE upload_id=%s",(audit,upload)),"Document cannot bind internal Audit file")
                denied(lambda:db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',available_at='infinity',lock_version=1 WHERE file_object_id=%s",(audit,)))
                db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',available_at=clock_timestamp(),lock_version=1 WHERE file_object_id=%s",(audit,))
                denied(lambda:f.schema.insert(db,"doc_document_versions",dict(document_id=document,scope="PROJECT",project_id=project,
                    version_no=1,file_object_id=audit,content_sha256=b"h"*32,size_bytes=0,detected_mime="application/x-ndjson",created_by=actor),"document_version_id"),"Document cannot bind internal Audit file")
                # Ordinary same-project upload and immutable version still work.
                db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=1 WHERE upload_id=%s",(old_files[0],upload))
                db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',available_at=clock_timestamp(),lock_version=1 WHERE file_object_id=%s",(old_files[0],))
                version=f.schema.insert(db,"doc_document_versions",dict(document_id=document,scope="PROJECT",project_id=project,version_no=1,
                    file_object_id=old_files[0],content_sha256=b"h"*32,size_bytes=0,detected_mime="application/x-ndjson",created_by=actor),"document_version_id")
                assert version
                db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED',lock_version=2 WHERE file_object_id=%s",(audit,))
                denied(lambda:db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',lock_version=3 WHERE file_object_id=%s",(audit,)))
                db.execute("UPDATE plm.doc_file_objects SET file_state='FAILED',lock_version=1 WHERE file_object_id=%s",(deployment,))
                for identity in (audit,deployment): denied(lambda identity=identity:db.execute("DELETE FROM plm.doc_file_objects WHERE file_object_id=%s",(identity,)))
                denied(lambda:db.execute("TRUNCATE plm.doc_file_objects CASCADE"))
                history=tuple(db.execute("SELECT * FROM plm.doc_file_objects ORDER BY file_object_id"))
                try:
                    with patch("alembic.op.execute",side_effect=locked): command.downgrade(cfg,"20260926_0039")
                except RuntimeError as exc: assert "Audit file history exists" in str(exc)
                else: raise AssertionError("Audit history lost on downgrade")
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()==("20260926_0040",)
                assert tuple(db.execute("SELECT * FROM plm.doc_file_objects ORDER BY file_object_id"))==history
            print("P03-A01 PASS: actual empty/old DOCUMENT data up/down/reup/ORM parity; Audit Scope/usage/identity/state/history guards; actual same-PROJECT Upload/Version misbinding rejected and ordinary binding preserved; actual downgrade lock/history refusal. Synthetic owner UUID, no Export/Lease/File/HTTP delivery proof.")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
