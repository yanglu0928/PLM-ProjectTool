"""Actual Session and current project/admin authorization over original dualScope uploads."""
import hashlib
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService, JobGetQuery, JobReadError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.document.application.parse_job_result import DocumentParseJobResults
from plm_assistant.modules.document.infrastructure.parse_job_result import SqlAlchemyDocumentParseJobResults

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('_authority_upload_sources', ROOT / 'job-01-a04-p02-document-source' / 'verify.py')
base = module_from_spec(spec); spec.loader.exec_module(base)
authspec = spec_from_file_location('_authority_doc_users', ROOT / 'doc-01-a02-document-read' / 'verify.py')
auth = module_from_spec(authspec); authspec.loader.exec_module(auth)


def observe(v, global_result, *, runtime_observer=None):
    queue = ParseJobQueue(SqlAlchemyParseJobQueueRepository())
    sources = DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(),
        audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources()))
    guard = auth.Guard()
    reader = AuthorizedJobReadService(unit_of_work=v['runtime'].unit_of_work,
        project_access=SqlAlchemyProjectReadAccess(), deployment_access=SqlAlchemyDeploymentReadAccess(),
        projects=ProjectAuthorizationService(unit_of_work=v['runtime'].unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=guard, repository=SqlAlchemyJobReadRepository(),
        owners={('document', 'DOCUMENT_PARSE'): DocumentParseJobReadProjection(queue=queue, sources=sources,
            results=DocumentParseJobResults(repository=SqlAlchemyDocumentParseJobResults()))})
    router = create_job_detail_router(reads=reader, origins=LoginOriginPolicy(['https://plm.example.test']))
    with base.fixture.connect(v['name']) as db, TestClient(create_app(job_detail_router=router), base_url='https://plm.example.test') as client:
        token = b'P' * 32
        # Existing immutable original actor stays intact. Test credential is not a login proof.
        credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}') RETURNING password_credential_id", (v['actor'],)).fetchone()[0]
        db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential, v['actor']))
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES(%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(b'C' * 32).digest(), v['actor']))
        im_token, customer_token, admin_token = b'I' * 32, b'M' * 32, b'A' * 32
        im = auth.user(db, 'Synthetic Parse IM', im_token)
        customer = auth.user(db, 'Synthetic Parse Customer', customer_token)
        admin = auth.user(db, 'Synthetic Parse Admin', admin_token, admin=True)
        dept = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES(%s,'READ','read','Synthetic read department') RETURNING department_id", (v['project'],)).fetchone()[0]
        for user, role in ((v['actor'], 'PROJECT_MANAGER'), (im, 'IMPLEMENTATION_MEMBER'), (customer, 'CUSTOMER_MEMBER')):
            db.execute('INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES(%s,%s,%s,%s)', (v['project'], user, dept, role))
        tables = ('job_jobs', 'job_outbox_events', 'doc_upload_intents', 'doc_documents', 'doc_document_versions',
            'doc_version_source_refs', 'doc_file_objects', 'aud_events', 'plt_idempotency_receipts',
            'auth_users', 'auth_sessions', 'prj_project_members', 'prj_departments', 'doc_parse_records', 'doc_parse_result_refs')
        def snapshot():
            return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        def read(q):
            before = snapshot(); result = reader.get(q)
            response = client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex(), 'if-none-match': '"v0"'})
            assert response.status_code == 200
            data = response.json()['data']
            assert data['job_id'] == str(q.job_id) and data['scope'] == result.facts.scope
            assert data['state'] == result.facts.state
            assert data['result_ref'] == ({'type': result.owner.result_type, 'id': str(result.owner.result_id)} if result.owner.result_id else None)
            assert data['etag'] == response.headers['etag'] == f'"v{result.facts.lock_version}"'
            assert response.headers['cache-control'] == 'no-store'
            assert not any(key in data for key in ('actor_id', 'payload_refs', 'storage_locator', 'worker_ref', 'fencing_token'))
            assert snapshot() == before
            assert result.facts.job_id == q.job_id
            return result
        def path(q):
            return f'/api/v1/projects/{q.project_id}/jobs/{q.job_id}' if q.project_id else f'/api/v1/admin/jobs/{q.job_id}'
        def deny(q, code):
            before = snapshot()
            try: reader.get(q)
            except JobReadError as exc: assert exc.code == code, (exc.code, code)
            else: raise AssertionError('Current authority improperly granted')
            response = client.get(path(q), headers={'cookie': 'plm_session=' + q.session_token.hex(), 'if-none-match': '"v0"'})
            assert response.status_code == {'AUTH_ACCESS_DENIED': 401, 'RESOURCE_NOT_FOUND': 404, 'LICENSE_OPERATION_DENIED': 403}.get(code, 503)
            assert set(response.json()) == {'error', 'trace_id'}
            assert snapshot() == before
        q = JobGetQuery(token, v['project'], uuid4(), v['first'].parse_job_id)
        for original in (v['first'], v['second'], v['recovered']):
            read(replace(q, job_id=original.parse_job_id))
        read(replace(q, session_token=im_token))
        deny(replace(q, session_token=customer_token), 'RESOURCE_NOT_FOUND')
        deny(replace(q, session_token=b'?' * 32), 'AUTH_ACCESS_DENIED')
        deny(replace(q, project_id=uuid4()), 'RESOURCE_NOT_FOUND')
        deny(replace(q, project_id=None, session_token=admin_token), 'RESOURCE_NOT_FOUND')
        deny(replace(q, job_id=uuid4()), 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' WHERE user_id=%s", (v['actor'],))
        read(q)  # creator-only customer reads the original task, not another actor's.
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE user_id=%s", (v['actor'],))
        deny(q, 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',project_role='PROJECT_MANAGER' WHERE user_id=%s", (v['actor'],))
        db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (dept,))
        deny(q, 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s", (dept,))
        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (v['actor'],))
        deny(q, 'AUTH_ACCESS_DENIED')
        db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s", (v['actor'],))
        global_q = JobGetQuery(admin_token, None, uuid4(), global_result.parse_job_id)
        read(global_q)
        if runtime_observer is not None: runtime_observer(v, (q, global_q))
        deny(replace(global_q, session_token=token), 'AUTH_ACCESS_DENIED')
        deny(replace(global_q, project_id=v['project'], session_token=token), 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s", (admin,))
        deny(global_q, 'AUTH_ACCESS_DENIED')
        db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s", (admin,))
        guard.enabled = False
        deny(q, 'LICENSE_OPERATION_DENIED'); deny(global_q, 'LICENSE_OPERATION_DENIED')
        guard.enabled = True
        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (im,))
        deny(replace(q, session_token=im_token), 'AUTH_ACCESS_DENIED')
        # Irreversible restriction is ONLY in this disposable fixture; no false restoration.
        db.execute("UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' WHERE document_version_id=%s", (v['first'].document_version_id,))
        deny(q, 'RESOURCE_NOT_FOUND')
        file_id = db.execute('SELECT file_object_id FROM plm.doc_document_versions WHERE document_version_id=%s', (v['recovered'].document_version_id,)).fetchone()[0]
        db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED',lock_version=lock_version+1 WHERE file_object_id=%s", (file_id,))
        deny(replace(q, job_id=v['recovered'].parse_job_id), 'RESOURCE_NOT_FOUND')
        read(replace(q, job_id=v['second'].parse_job_id)); read(global_q)
        with TestClient(create_app()) as default:
            assert default.get(path(global_q)).status_code == 404
        assert client.get(path(global_q) + '?scope=PROJECT', headers={'cookie': 'plm_session=' + admin_token.hex()}).status_code == 400
        assert client.get(path(global_q), headers={'cookie': 'plm_session=' + admin_token.hex(), 'host': 'evil.test'}).status_code == 403
    print('JOB-01-A04-P03 authority+HTTP PASS: actual Session/current PM-IM/creator customer and Admin GLOBAL over four real source commitments; revoked/disabled/member/department/admin/License/crossScope/ref/source restrictions reject fifteen tables no read writes, optional ASGI state/ETag/logical result/no-store/conditional refusal/default404. Credential TEST_ONLY and License synthetic; Parser history and runtime callback tested separately, no login/Parser execution/package/Gate claim.')


if __name__ == '__main__':
    base.fixture.verify(exercise=lambda v: base.exercise(v, observe=observe))
