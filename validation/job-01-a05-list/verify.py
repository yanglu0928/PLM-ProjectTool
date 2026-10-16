"""Actual current Session/Project/Admin and Source-proven keyset list, no public cursor yet."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.jobs.application.authorized_list import AuthorizedJobListService, JobListQuery
from plm_assistant.modules.jobs.application.authorized_read import JobReadError
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection

spec = spec_from_file_location('_job_list_authority', Path(__file__).resolve().parents[1] / 'job-01-a04-p03-authority' / 'verify.py')
authority = module_from_spec(spec); spec.loader.exec_module(authority)


def observe(v, queries):
    guard = authority.auth.Guard()
    queue = authority.ParseJobQueue(authority.SqlAlchemyParseJobQueueRepository())
    reader = AuthorizedJobListService(unit_of_work=v['runtime'].unit_of_work,
        project_access=authority.SqlAlchemyProjectReadAccess(), deployment_access=authority.SqlAlchemyDeploymentReadAccess(),
        projects=authority.ProjectAuthorizationService(unit_of_work=v['runtime'].unit_of_work, repository=authority.SqlAlchemyProjectAuthorizationRepository()),
        license_guard=guard, repository=SqlAlchemyJobReadRepository(), owners={('document', 'DOCUMENT_PARSE'):
            DocumentParseJobReadProjection(queue=queue, sources=authority.DocumentParseSourceReader(repository=authority.SqlAlchemyDocumentParseSources(),
                audit_sources=authority.UploadCommitAuditSources(repository=authority.SqlAlchemyUploadCommitAuditSources())))})
    with authority.base.fixture.connect(v['name']) as db:
        tables = ('job_jobs', 'job_outbox_events', 'doc_upload_intents', 'doc_documents', 'doc_document_versions', 'doc_version_source_refs',
            'doc_file_objects', 'aud_events', 'plt_idempotency_receipts', 'auth_users', 'auth_sessions', 'prj_project_members', 'prj_departments')
        def snapshot(): return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        project_q = JobListQuery(queries[0].session_token, v['project'], queries[0].trace_id, 1)
        global_q = JobListQuery(queries[1].session_token, None, queries[1].trace_id, 1)
        # Same timestamps prove UUID tie-breaks, not accidental unique time ordering.
        stamp = db.execute("SELECT min(created_at) FROM plm.job_jobs WHERE scope='PROJECT'").fetchone()[0]
        db.execute("UPDATE plm.job_jobs SET created_at=%s WHERE owner_module='document' AND scope='PROJECT'", (stamp,))
        def collect(q):
            ids, pages, positions = [], [], set()
            while True:
                before = snapshot(); page = reader.list(q); assert snapshot() == before
                pages.append(page); ids.extend(item.facts.job_id for item in page.items)
                if not page.has_more: break
                assert page.next_position not in positions
                positions.add(page.next_position); assert len(positions) <= 5
                q = replace(q, before=page.next_position)
            assert len(ids) == len(set(ids))
            return ids, pages
        expected = {v['first'].parse_job_id, v['second'].parse_job_id, v['recovered'].parse_job_id}
        ids, pages = collect(project_q); assert set(ids) == expected and len(pages) == 3
        assert ids == sorted(ids, reverse=True)
        global_ids, _ = collect(global_q); assert global_ids == [queries[1].job_id]
        assert reader.list(replace(global_q, scope='DEPLOYMENT')).items == ()
        def deny(q, code):
            before = snapshot()
            try: reader.list(q)
            except JobReadError as exc: assert exc.code == code
            else: raise AssertionError('Unauthorized list accepted')
            assert snapshot() == before
        deny(replace(project_q, session_token=b'?' * 32), 'AUTH_ACCESS_DENIED')
        deny(replace(global_q, session_token=queries[0].session_token), 'AUTH_ACCESS_DENIED')
        deny(replace(project_q, project_id=authority.uuid4()), 'RESOURCE_NOT_FOUND')
        deny(replace(project_q, session_token=queries[1].session_token), 'RESOURCE_NOT_FOUND')
        customer = db.execute("SELECT user_id FROM plm.auth_users WHERE username_normalized='synthetic parse customer'").fetchone()[0]
        im = db.execute("SELECT user_id FROM plm.auth_users WHERE username_normalized='synthetic parse im'").fetchone()[0]
        assert collect(replace(project_q, session_token=b'I' * 32))[0] == ids
        assert reader.list(replace(project_q, session_token=b'M' * 32)).items == ()
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE user_id=%s", (v['actor'],))
        deny(project_q, 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE' WHERE user_id=%s", (v['actor'],))
        db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE project_id=%s", (v['project'],))
        deny(project_q, 'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE project_id=%s", (v['project'],))
        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (v['actor'],))
        deny(project_q, 'AUTH_ACCESS_DENIED')
        db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s", (v['actor'],))
        db.execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s', (v['other'], v['recovered'].parse_job_id))
        deny(replace(project_q, page_size=50), 'JOB_UNAVAILABLE')
        db.execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s', (v['actor'], v['recovered'].parse_job_id))
        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' WHERE user_id=%s", (v['actor'],))
        assert collect(project_q)[0] == ids
        db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE user_id=%s", (v['actor'],))
        db.execute("UPDATE plm.doc_documents SET document_state='RESTRICTED',lock_version=lock_version+1 WHERE document_id=%s", (v['first'].document_id,))
        hidden_ids, hidden_pages = collect(project_q)
        assert hidden_ids == [v['recovered'].parse_job_id] and len(hidden_pages) == 3
        assert any(not page.items and page.has_more for page in hidden_pages)
        db.execute("UPDATE plm.doc_documents SET document_state='ACTIVE',lock_version=lock_version+1 WHERE document_id=%s", (v['first'].document_id,))
        guard.enabled = False
        deny(project_q, 'LICENSE_OPERATION_DENIED'); guard.enabled = True
        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (customer,))
        deny(replace(project_q, session_token=b'M' * 32), 'AUTH_ACCESS_DENIED')
    print('JOB list INTERNAL PASS: true current Session/Project/Admin, actual committed source and pair per item, same-time UUID keyset three pages no repeats/gaps; PM/IM, own customer/empty other customer, GLOBAL excludes PROJECT/DEPLOYMENT filter, hidden candidates bounded empty-page progress, thirteen tables no read writes. No public cursor/HTTP/runtime/fullOwner/performance/Gate proof.')


if __name__ == '__main__':
    authority.base.fixture.verify(exercise=lambda v: authority.base.exercise(v, observe=lambda v, g: authority.observe(v, g, runtime_observer=observe)))
