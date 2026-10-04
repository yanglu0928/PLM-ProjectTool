"""Own result/source/canonical bytes integrity. Job/File/SYSTEM identity refs synthetic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from io import BytesIO
import hashlib,json
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4,UUID
import psycopg
from psycopg import sql
from alembic import command,op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.audit.infrastructure.export_orm import results
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec,AuditExportAuthorityRequest
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource

load=spec_from_file_location('_result_schema_fixture',Path(__file__).resolve().parents[1]/'aud-02-a01-authorized-read'/'verify.py')
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime='exportresults_'+uuid4().hex[:12],None
    with f.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url=URL.create('postgresql+psycopg',username='poc_admin',host='127.0.0.1',port=55432,database=name)
            cfg=create_migration_config(url)
            command.upgrade(cfg,'head');command.downgrade(cfg,'20260926_0041');command.upgrade(cfg,'head')
            engine=create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs=compare_metadata(MigrationContext.configure(conn,opts={'include_schemas':True,
                        'include_object':lambda obj,name,type_,reflected,compare_to:name=='aud_export_results' if type_=='table' else True}),Base.metadata)
                    assert not diffs,str(diffs)
            finally:engine.dispose()
            command.downgrade(cfg,'20260926_0041');runtime=create_database_runtime(url)
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,'Synthetic schema result',b'r'*32,'DEPLOYMENT_ADMIN')
                project=f.schema.insert(db,'prj_projects',dict(project_code='RESULT',project_code_normalized='result',name='Synthetic results',created_by=actor),'project_id')
                oldfile=f.schema.insert(db,'doc_file_objects',dict(scope='GLOBAL',storage_class='PERSISTENT',storage_locator='global/'+uuid4().hex,original_name_metadata='synthetic.jsonl',created_by=actor,sha256=b'h'*32,size_bytes=0,detected_mime='application/x-ndjson'),'file_object_id')
                document=f.schema.insert(db,'doc_documents',dict(scope='GLOBAL',document_category='REFERENCE_MATERIAL',title='Synthetic old result-schema doc',original_display_name='synthetic.jsonl',created_by=actor),'document_id')
                db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',available_at=clock_timestamp(),lock_version=1 WHERE file_object_id=%s",(oldfile,))
                f.schema.insert(db,'doc_document_versions',dict(document_id=document,scope='GLOBAL',version_no=1,file_object_id=oldfile,content_sha256=b'h'*32,size_bytes=0,detected_mime='application/x-ndjson',created_by=actor),'document_version_id')
                def root(scope='DEPLOYMENT',nonempty=False,filtered=False):
                    now=datetime.now(timezone.utc);trace=uuid4();job=uuid4();source_trace=uuid4()
                    spec=AuditExportSpec(scope,project if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now+timedelta(hours=1),action='SYNTHETIC_SOURCE' if nonempty else 'SYNTHETIC_EMPTY',outcome='SUCCESS' if filtered else None,actor_id=actor if filtered else None,target_object_type='JOB-01' if filtered else None,target_object_id=job if filtered else None,trace_id=source_trace if filtered else None)
                    export=f.schema.insert(db,'aud_exports',dict(actor_id=actor,scope=scope,project_id=spec.project_id,trace_id=trace,purpose=spec.purpose,start_at=spec.start_at,end_at=spec.end_at,
                        action=spec.action,outcome=spec.outcome,filter_actor_id=spec.actor_id,target_object_type=spec.target_object_type,target_object_id=spec.target_object_id,filter_trace_id=spec.trace_id,
                        policy_version='AUDIT-EXPORT-POLICY-V1',projection_version='AUDIT-EVENT-SAFE-V1',format_version='JSONL_V1',intent_hash=spec.fingerprint()),'export_id')
                    request_event=f.schema.insert(db,'aud_events',dict(trace_id=trace,event_scope=scope,target_project_id=spec.project_id,actor_type='USER',actor_id=actor,action='AUDIT_EXPORT_REQUESTED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job,reason_code=spec.purpose,after_state='PENDING'),'audit_event_id')
                    f.schema.insert(db,'aud_export_acceptances',dict(export_id=export,job_id=job,event_id=uuid4(),request_audit_event_id=request_event),'export_id')
                    if nonempty:f.schema.insert(db,'aud_events',dict(trace_id=source_trace,event_scope=scope,target_project_id=spec.project_id,actor_type='USER',actor_id=actor,action='SYNTHETIC_SOURCE',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job),'audit_event_id')
                    requested=db.execute('SELECT requested_at FROM plm.aud_exports WHERE export_id=%s',(export,)).fetchone()[0]
                    intent=AuditExportIntent(export,actor,trace,requested,spec,spec.fingerprint())
                    with runtime.unit_of_work() as tx:
                        capture=SqlAlchemyAuditCaptureRepository().capture(tx,request=AuditExportAuthorityRequest(export,actor,scope,spec.project_id,'CAPTURE'));tx.commit()
                    file_id=uuid4()
                    plan=f.schema.insert(db,'aud_export_render_attempts',dict(export_id=export,job_id=job,fencing_token=1,attempt_no=1,worker_ref='synthetic-schema-worker',file_id=file_id,member_count=capture.member_count,membership_hash=capture.membership_hash,membership_version=capture.membership_version),'render_attempt_id')
                    with runtime.unit_of_work() as tx:
                        rendered=AuditExportRenderer().render(intent=intent,capture=capture,items=SqlAlchemyAuditExportRenderSource().iter_events(tx,export_id=export),sink=BytesIO())
                    event_values=dict(trace_id=trace,event_scope=scope,target_project_id=spec.project_id,actor_type='SYSTEM',actor_id=uuid4(),original_actor_id=actor,action='AUDIT_EXPORT_PUBLISHED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job,reason_code=spec.purpose,before_state='RUNNING',after_state='SUCCEEDED')
                    published=f.schema.insert(db,'aud_events',event_values,'audit_event_id')
                    values=dict(export_id=export,render_attempt_id=plan,file_id=file_id,file_sha256=bytes.fromhex(rendered.file_sha256),byte_count=rendered.byte_count,mime_type='application/x-ndjson',manifest_version='AUDIT-EXPORT-MANIFEST-V1',manifest_bytes=rendered.manifest_bytes,manifest_sha256=hashlib.sha256(rendered.manifest_bytes).digest(),publish_audit_event_id=published)
                    return values,event_values
                fixtures=[root(),root('PROJECT'),root(nonempty=True,filtered=True),root('PROJECT',True,True)]
                tables=('aud_exports','aud_export_acceptances','aud_export_captures','aud_export_members','aud_export_render_attempts','aud_events','doc_file_objects','doc_documents','doc_document_versions')
                def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
                old=snapshot();command.upgrade(cfg,'head');assert snapshot()==old
                assert db.execute('SELECT count(*) FROM plm.aud_export_results').fetchone()==(0,)
                execute=op.execute
                def locked(statement,*args,**kwargs):
                    result=execute(statement,*args,**kwargs)
                    if str(statement)=='LOCK TABLE plm.aud_export_results IN ACCESS EXCLUSIVE MODE':
                        def competitor():
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='100ms'")
                                try:
                                    with rival.transaction():rival.execute('LOCK TABLE plm.aud_export_results IN ROW EXCLUSIVE MODE')
                                except psycopg.errors.LockNotAvailable:return True
                                return False
                        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competitor).result()
                    return result
                with patch('alembic.op.execute',side_effect=locked):command.downgrade(cfg,'20260926_0041')
                assert snapshot()==old;command.upgrade(cfg,'head');assert snapshot()==old
                def insert(v,conn=db):return f.schema.insert(conn,'aud_export_results',v,'export_id')
                def denied(action):
                    try:
                        with db.transaction():action()
                    except (psycopg.errors.RaiseException,psycopg.errors.CheckViolation,psycopg.errors.ForeignKeyViolation,psycopg.errors.UniqueViolation,psycopg.errors.NotNullViolation):return
                    raise AssertionError('invalid or destructive result accepted')
                v,event=fixtures[0]
                for changes in (dict(export_id=uuid4()),dict(render_attempt_id=uuid4()),dict(render_attempt_id=fixtures[1][0]['render_attempt_id']),dict(file_id=uuid4()),dict(file_id=UUID(int=0)),dict(file_sha256=b'x'),dict(file_sha256=b'x'*32),dict(byte_count=-1),dict(byte_count=134217729),dict(byte_count=1),dict(mime_type='application/pdf'),dict(manifest_version='OTHER'),dict(manifest_sha256=b'x'*32),dict(publish_audit_event_id=uuid4()),dict(publish_audit_event_id=fixtures[1][0]['publish_audit_event_id']),dict(published_at='infinity'),dict(published_at=datetime.now(timezone.utc)-timedelta(days=1))):
                    denied(lambda changes=changes:insert(v|changes))
                malformed=[b'',b'{}\n',v['manifest_bytes'].rstrip(b'\n'),b'\xef\xbb\xbf'+v['manifest_bytes'],v['manifest_bytes']+b' ',b'x'*8193]
                obj=json.loads(v['manifest_bytes'])
                malformed.append(json.dumps(obj,sort_keys=True).encode()+b'\n')
                for key in obj:
                    modified=dict(obj);modified[key]='forged'
                    malformed.append(json.dumps(modified,sort_keys=True,separators=(',',':')).encode()+b'\n')
                for key in obj['filters']:
                    modified=dict(obj);modified['filters']=dict(obj['filters']);modified['filters'][key]='forged'
                    malformed.append(json.dumps(modified,sort_keys=True,separators=(',',':')).encode()+b'\n')
                modified=dict(obj);del modified['filters'];malformed.append(json.dumps(modified,sort_keys=True,separators=(',',':')).encode()+b'\n')
                modified=dict(obj);modified['unexpected']='secret body';malformed.append(json.dumps(modified,sort_keys=True,separators=(',',':')).encode()+b'\n')
                malformed.append(v['manifest_bytes'].replace(b'{',b'{"scope":"DEPLOYMENT",',1))
                for payload in malformed:denied(lambda payload=payload:insert(v|dict(manifest_bytes=payload,manifest_sha256=hashlib.sha256(payload).digest())))
                nonempty=fixtures[2][0];empty_obj=json.loads(nonempty['manifest_bytes']);empty_obj['byte_count']=0;empty_obj['file_sha256']=hashlib.sha256(b'').hexdigest()
                empty_payload=json.dumps(empty_obj,sort_keys=True,separators=(',',':')).encode()+b'\n'
                denied(lambda:insert(nonempty|dict(byte_count=0,file_sha256=hashlib.sha256(b'').digest(),manifest_bytes=empty_payload,manifest_sha256=hashlib.sha256(empty_payload).digest())))
                for changes in (dict(actor_type='USER',original_actor_id=None),dict(original_actor_id=uuid4()),dict(trace_id=uuid4()),dict(event_scope='PROJECT',target_project_id=project),dict(action='OTHER'),dict(outcome='FAILED'),dict(target_object_id=uuid4()),dict(reason_code='OTHER'),dict(before_state=None),dict(after_state='FAILED'),dict(target_version_id=uuid4()),dict(occurred_at=datetime.now(timezone.utc)-timedelta(days=1))):
                    with db.transaction():
                        fake=f.schema.insert(db,'aud_events',event|changes,'audit_event_id')
                        denied(lambda:insert(v|dict(publish_audit_event_id=fake)))
                # No result source changed during denied inserts; extra synthetic Audit events are retained.
                old=snapshot()
                for values,_ in fixtures:assert insert(values)==values['export_id']
                denied(lambda:insert(v))
                history=tuple(db.execute('SELECT * FROM plm.aud_export_results ORDER BY export_id'))
                for action in (lambda:db.execute('UPDATE plm.aud_export_results SET byte_count=byte_count WHERE export_id=%s',(v['export_id'],)),lambda:db.execute('DELETE FROM plm.aud_export_results WHERE export_id=%s',(v['export_id'],)),lambda:db.execute('TRUNCATE plm.aud_export_results')):denied(action)
                race,_=root('PROJECT');barrier=Barrier(2)
                def competing(_):
                    with f.schema.connect(name) as rival:
                        barrier.wait()
                        try:return insert(race,rival)
                        except psycopg.errors.UniqueViolation:return None
                with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(competing,(0,1)))
                assert sum(v is not None for v in pair)==1
                old=snapshot();history=tuple(db.execute('SELECT * FROM plm.aud_export_results ORDER BY export_id'))
                try:
                    with patch('alembic.op.execute',side_effect=locked):command.downgrade(cfg,'20260926_0041')
                except RuntimeError as exc:assert 'Audit result history exists' in str(exc)
                else:raise AssertionError('result history lost')
                assert db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260926_0042',)
                assert snapshot()==old and tuple(db.execute('SELECT * FROM plm.aud_export_results ORDER BY export_id'))==history
            print('P03-A03-P03 PASS: empty/old plan up/down/reup/parity/no guessed result, own source/audit/time/UUID/shape guards, actual renderer canonical manifests both scopes empty/nonempty/filtered, all manifest fields/whitespace/extra/duplicate-key and hashes reject, concurrent unique/immutable/down locking/history preservation. Job/File/SystemActor refs synthetic, memory bytes only; NOT actual file/authority/lease/atomic Job success/publication/HTTP proof.')
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__=='__main__':main()
