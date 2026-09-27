"""Real constrained parse metadata history; deliberately not a Parser execution claim."""
import hashlib
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.document.application.parse_job_result import DocumentParseJobResults
from plm_assistant.modules.document.infrastructure.parse_job_result import SqlAlchemyDocumentParseJobResults
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.jobs.application.authorized_read import JobReadError

spec = spec_from_file_location('_result_source_commits', Path(__file__).resolve().parents[1] / 'job-01-a04-p02-document-source' / 'verify.py')
base = module_from_spec(spec); spec.loader.exec_module(base)


def observe(v, global_result):
    queue = base.ParseJobQueue(base.SqlAlchemyParseJobQueueRepository())
    sources = base.DocumentParseSourceReader(repository=base.SqlAlchemyDocumentParseSources(),
        audit_sources=base.UploadCommitAuditSources(repository=base.SqlAlchemyUploadCommitAuditSources()))
    results = DocumentParseJobResults(repository=SqlAlchemyDocumentParseJobResults())
    owner = DocumentParseJobReadProjection(queue=queue, sources=sources, results=results)
    facts_repo = SqlAlchemyJobReadRepository()
    with base.fixture.connect(v['name']) as db:
        tables = ('job_jobs', 'job_outbox_events', 'doc_upload_intents', 'doc_documents', 'doc_document_versions',
            'doc_version_source_refs', 'doc_file_objects', 'aud_events', 'plt_idempotency_receipts', 'doc_parse_records', 'doc_parse_result_refs')
        def snapshot(): return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        def seed(result, attempt):
            record = db.execute("INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,parser_profile,parser_version,job_ref,attempt_no) SELECT document_version_id,scope,project_id,'TEST_METADATA','1',%s,%s FROM plm.doc_document_versions WHERE document_version_id=%s RETURNING parse_record_id", (result.parse_job_id, attempt, result.document_version_id)).fetchone()[0]
            db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',started_at=statement_timestamp(),lock_version=lock_version+1 WHERE parse_record_id=%s", (record,))
            digest = hashlib.sha256(b'Synthetic metadata result, not executed Parser').digest()
            ref = db.execute("INSERT INTO plm.doc_parse_result_refs(parse_record_id,storage_locator,result_schema_version,sha256,size_bytes) VALUES(%s,%s,1,%s,0) RETURNING parse_result_ref_id", (record, 'synthetic/metadata/' + record.hex, digest)).fetchone()[0]
            db.execute("UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,retryable=false,lock_version=lock_version+1 WHERE parse_record_id=%s", (ref, digest, record))
            return record
        for original in (v['first'], global_result):
            record = seed(original, 1)
            db.execute("UPDATE plm.job_jobs SET state='RUNNING',attempt_count=1 WHERE job_id=%s", (original.parse_job_id,))
            db.execute("UPDATE plm.job_jobs SET state='SUCCEEDED',completed_at=statement_timestamp() WHERE job_id=%s", (original.parse_job_id,))
            before = snapshot()
            with v['runtime'].unit_of_work() as tx:
                facts = facts_repo.get(tx, job_id=original.parse_job_id)
                projected = owner.project(tx, facts=facts, actor_id=v['actor'], project_role='PROJECT_MANAGER' if original is v['first'] else None)
                assert (projected.result_type, projected.result_id) == ('DOCUMENT_PARSE', record)
                assert facts_repo.get(tx, job_id=facts.job_id) == facts
                binding = queue.peek_parse_for_job(tx, job_id=facts.job_id)
                source = sources.read(tx, request=binding.request)
                for wrong in (replace(source, request=replace(source.request, document_version_id=uuid4())),
                    replace(source, request=replace(source.request, actor_id=uuid4()))):
                    try: results.read(tx, facts=facts, source=wrong)
                    except JobReadError: pass
                    else: raise AssertionError('Incorrect successful source accepted')
            assert snapshot() == before
        # Schema permits another successful profile attempt; reader must refuse ambiguity.
        seed(global_result, 2)
        before = snapshot()
        with v['runtime'].unit_of_work() as tx:
            facts = facts_repo.get(tx, job_id=global_result.parse_job_id)
            try: owner.project(tx, facts=facts, actor_id=v['actor'], project_role=None)
            except JobReadError as exc: assert exc.code == 'JOB_UNAVAILABLE'
            else: raise AssertionError('Ambiguous success accepted')
        assert snapshot() == before
    print('Parse result source INTERNAL PASS: actual constrained PROJECT/GLOBAL ParseRecord/immutable ResultRef metadata and Job state, exact logical ref/old-version origin, wrong provenance and duplicate success reject eleven tables no read writes. Histories directly seeded, no actual Parser/Lease/byte integrity/quality/HTTP/runtime/Gate claim.')


if __name__ == '__main__': base.fixture.verify(exercise=lambda v: base.exercise(v, observe=observe))
