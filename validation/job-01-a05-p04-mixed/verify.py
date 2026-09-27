"""Actual Audit publication + Document file commitments in one isolated list matrix."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
import hashlib
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.jobs.application.authorized_list import AuthorizedJobListService, JobListQuery
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.jobs.api.list_jobs import create_job_list_router
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.document.application.parse_job_result import DocumentParseJobResults
from plm_assistant.modules.document.infrastructure.parse_job_result import SqlAlchemyDocumentParseJobResults
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources

ROOT = Path(__file__).resolve().parents[1]


def load(name, folder):
    spec = spec_from_file_location(name, ROOT / folder / 'verify.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module


fixture = load('_mixed_list_audit_publication', 'aud-03-a06-a04-p03-a04-p03-publication')
doc = load('_mixed_list_doc_upload', 'doc-03-a04-a04-upload-commit')


def exercise(v, *, observe_runtime=None):
    db = v['db']; storage = doc.LocalFileStorage(v['file_root'])
    document_queue = doc.ParseJobQueue(doc.SqlAlchemyParseJobQueueRepository())
    documents = []
    for scope, actor in (('PROJECT', v['users'][0]), ('GLOBAL', v['users'][1])):
        upload = uuid4(); content = b'%PDF-1.7\nSynthetic mixed list real source' * 24
        pid = v['project'] if scope == 'PROJECT' else None
        stage, final = storage.locators(scope=scope, project_id=pid, file_object_id=upload)
        with storage.reserve_staging(stage) as stream: stream.write(content)
        digest = hashlib.sha256(content).digest()
        db.execute("INSERT INTO plm.doc_upload_intents(upload_id,scope,project_id,actor_id,document_category,title,original_display_name,purpose_code,token_digest,expires_at) VALUES(%s,%s,%s,%s,'REFERENCE_MATERIAL','Synthetic mixed source','mixed.pdf','SOURCE_UPLOAD',%s,statement_timestamp()+interval '15 minutes')", (upload, scope, pid, actor, hashlib.sha256(upload.bytes).digest()))
        db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES(%s,%s,%s,'PERSISTENT',%s,'mixed.pdf',%s,%s,'application/pdf',%s)", (upload, scope, pid, stage, digest, len(content), actor))
        db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=lock_version+1 WHERE upload_id=%s", (upload, upload))
        commit = doc.CommitUploadService(unit_of_work=v['runtime'].unit_of_work, access=doc.Access(actor),
            repository=doc.SqlAlchemyUploadCommitRepository(), receipts=doc.SqlAlchemyIdempotencyReceipts(), jobs=document_queue,
            audit=v['audit'], storage=storage, license_guard=v['guard'], operation_gate=doc.LocalUploadOperationGate(v['file_root']))
        original = commit.commit(doc.CommitUpload(upload, scope, pid, actor, uuid4(), None, len(content)), idempotency_key=str(uuid4()))
        assert storage.verify_content(final, expected_sha256=digest, expected_size=len(content), max_bytes=len(content))
        documents.append(original)
        # Fixture only: do not let the original Audit-only final claim consume a Parser Job.
        db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp()+interval '1 year' WHERE job_id=%s", (original.parse_job_id,))
    running = [v['prepare'](scope, 3) for scope in ('PROJECT', 'DEPLOYMENT')]
    owners = {('audit', 'AUDIT_EXPORT'): AuditJobReadProjection(repository=v['repo'], queue=v['queue'], results=v['results']),
        ('document', 'DOCUMENT_PARSE'): DocumentParseJobReadProjection(queue=document_queue,
            sources=DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(), audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources())),
            results=DocumentParseJobResults(repository=SqlAlchemyDocumentParseJobResults()))}
    service = AuthorizedJobListService(unit_of_work=v['runtime'].unit_of_work, project_access=SqlAlchemyProjectReadAccess(),
        deployment_access=SqlAlchemyDeploymentReadAccess(), projects=v['projects'], license_guard=v['guard'], repository=SqlAlchemyJobReadRepository(), owners=owners)
    codec = JobListCursorCodec(b'J' * 32)
    router = create_job_list_router(reads=service, origins=LoginOriginPolicy(['https://plm.example.test']), cursors=codec)
    tables = ('job_jobs', 'job_outbox_events', 'job_leases', 'job_attempts', 'doc_upload_intents', 'doc_documents', 'doc_document_versions',
        'doc_version_source_refs', 'doc_file_objects', 'aud_events', 'plt_idempotency_receipts', 'aud_exports', 'aud_export_acceptances',
        'aud_export_results', 'auth_users', 'auth_sessions', 'prj_project_members', 'prj_departments')
    def snapshot(): return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    project_q = JobListQuery(v['tokens'][0], v['project'], uuid4(), 2)
    admin_q = JobListQuery(v['tokens'][1], None, uuid4(), 2)
    with TestClient(create_app(job_list_router=router), base_url='https://plm.example.test') as client:
        def path(q): return f'/api/v1/projects/{q.project_id}/jobs' if q.project_id else '/api/v1/admin/jobs'
        def collect(q):
            rows = []; positions = set()
            while True:
                before = snapshot(); page = service.list(q)
                params = {'page_size': str(q.page_size)}
                if q.scope is not None: params['scope'] = q.scope
                if q.before is not None: params['cursor'] = codec.encode(query=q, before=q.before)
                response = client.get(path(q), params=params, headers={'cookie': 'plm_session=' + q.session_token.hex()})
                assert response.status_code == 200
                data = response.json()['data']
                assert [item['job_id'] for item in data['items']] == [str(item.facts.job_id) for item in page.items]
                for public, detail in zip(data['items'], page.items):
                    assert public['state'] == detail.facts.state
                    assert public['result_ref'] == ({'type': detail.owner.result_type, 'id': str(detail.owner.result_id)} if detail.owner.result_id else None)
                assert snapshot() == before
                rows.extend(page.items)
                if not page.has_more:
                    assert data['next_cursor'] is None; break
                position = codec.decode(data['next_cursor'], query=q)
                assert position == page.next_position and position not in positions
                positions.add(position); assert len(positions) < 80
                q = replace(q, before=position)
            assert len(rows) == len({item.facts.job_id for item in rows})
            return rows
        for q in (project_q, admin_q):
            page_rows = collect(q)
            assert {item.facts.owner_module for item in page_rows} == {'audit', 'document'}
            expected = {row[0] for row in db.execute("SELECT job_id FROM plm.job_jobs WHERE project_id IS NOT DISTINCT FROM %s AND owner_module IN ('audit','document')", (q.project_id,))}
            assert {item.facts.job_id for item in page_rows} == expected
            assert any(item.facts.state == 'RUNNING' and item.facts.owner_module == 'audit' for item in page_rows)
            assert any(item.facts.state == 'PENDING' and item.facts.owner_module == 'document' for item in page_rows)
        # Actual worker publication, not direct synthetic success writes.
        for accepted, command, staged in running: v['worker'].publish(command, staged)
        for q, original in zip((project_q, admin_q), running):
            rows = collect(q)
            item = next(item for item in rows if item.facts.job_id == original[0].job_id)
            assert item.facts.state == 'SUCCEEDED' and item.owner.result_id == original[1].export_id
        assert {item.facts.job_id for item in collect(replace(admin_q, scope='GLOBAL'))} == {documents[1].parse_job_id}
        assert all(item.facts.owner_module == 'audit' for item in collect(replace(admin_q, scope='DEPLOYMENT')))
        # Mixed same timestamp stable tie-breaks without accidental time uniqueness.
        stamp = db.execute('SELECT min(created_at) FROM plm.job_jobs').fetchone()[0]
        db.execute('UPDATE plm.job_jobs SET created_at=%s', (stamp,))
        for q in (project_q, admin_q):
            rows = collect(q)
            assert [item.facts.job_id for item in rows] == sorted((item.facts.job_id for item in rows), reverse=True)
        im_token, customer_token = b'I' * 32, b'C' * 32
        im = fixture.base.auth.user(db, 'Synthetic mixed list IM', im_token, 'NONE')
        customer = fixture.base.auth.user(db, 'Synthetic mixed list customer', customer_token, 'NONE')
        for user, role in ((im, 'IMPLEMENTATION_MEMBER'), (customer, 'CUSTOMER_MEMBER')):
            fixture.base.schema.insert(db, 'prj_project_members', dict(project_id=v['project'], user_id=user,
                department_id=v['dept'], project_role=role), 'project_member_id')
        assert {item.facts.owner_module for item in collect(replace(project_q, session_token=im_token))} == {'audit', 'document'}
        assert collect(replace(project_q, session_token=customer_token)) == []
        for q, status in ((replace(project_q, session_token=v['tokens'][1]), 404),
            (replace(admin_q, session_token=v['tokens'][0]), 401),
            (replace(project_q, session_token=b'?' * 32), 401)):
            before = snapshot()
            assert client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex()}).status_code == status
            assert snapshot() == before
        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' WHERE user_id=%s", (v['users'][0],))
        assert all(item.facts.actor_id == v['users'][0] for item in collect(project_q))
        db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE user_id=%s", (v['users'][0],))
        db.execute("UPDATE plm.doc_documents SET document_state='RESTRICTED',lock_version=lock_version+1 WHERE document_id=%s", (documents[0].document_id,))
        assert documents[0].parse_job_id not in {item.facts.job_id for item in collect(project_q)}
        db.execute("UPDATE plm.doc_documents SET document_state='ACTIVE',lock_version=lock_version+1 WHERE document_id=%s", (documents[0].document_id,))
        before = snapshot(); v['guard'].enabled = False
        try:
            for q in (project_q, admin_q): assert client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex()}).status_code == 403
        finally: v['guard'].enabled = True
        assert snapshot() == before
        bad_job = running[0][0].job_id
        db.execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s', (uuid4(), bad_job))
        before = snapshot()
        assert client.get(path(project_q), params={'page_size': 200}, headers={'cookie': 'plm_session=' + project_q.session_token.hex()}).status_code == 503
        assert snapshot() == before
        db.execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s', (v['users'][0], bad_job))
    if observe_runtime is not None: observe_runtime(v)
    print('Mixed Job list PASS: actual Audit current-authority/Lease/file/result/publication and PROJECT/GLOBAL Document real source files share original Owner registry; PROJECT and admin GLOBAL+DEPLOYMENT pages complete/no duplicate/stable same-time UUID, RUNNING/PENDING then actual Audit SUCCEEDED logical refs, scope/customer/source restriction/License/bad actor refusal eighteen tables no read writes. Document available_at delay fixture-only to avoid original Audit-only claim. License/upload Access/test cursor injected; no Parser/Windows list runtime/performance/fullOwner/Gate/package claim.')


if __name__ == '__main__': fixture.main(exercise=exercise)
