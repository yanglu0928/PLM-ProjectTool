"""Real original upload Owner composition, not a current Session authorization proof."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository

spec = spec_from_file_location('_owner_upload_fixture', Path(__file__).resolve().parents[1] / 'doc-03-a04-a04-upload-commit' / 'verify.py')
fixture = module_from_spec(spec); spec.loader.exec_module(fixture)


def exercise(v):
    owner = DocumentParseJobReadProjection(
        queue=ParseJobQueue(SqlAlchemyParseJobQueueRepository()),
        sources=DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(),
            audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources())))
    repo = SqlAlchemyJobReadRepository()
    tables = ('job_jobs', 'job_outbox_events', 'doc_upload_intents', 'doc_documents',
        'doc_document_versions', 'doc_version_source_refs', 'doc_file_objects', 'aud_events', 'plt_idempotency_receipts')
    with fixture.connect(v['name']) as db:
        def snapshot():
            return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        before = snapshot()
        for result in (v['first'], v['second'], v['recovered']):
            with v['runtime'].unit_of_work() as tx:
                facts = repo.get(tx, job_id=result.parse_job_id)
                projected = owner.project(tx, facts=facts, actor_id=v['actor'], project_role='PROJECT_MANAGER')
                assert projected.job_id == result.parse_job_id
                assert projected.result_id is None and projected.retryable is False
                assert repo.get(tx, job_id=result.parse_job_id) == facts
        assert snapshot() == before
    print('JOB-01-A04-P03 Owner source composition PASS: three actual original PROJECT commitments, old version retained, actual source and locked Job/Outbox pair, nine tables unchanged. Current Session/GLOBAL/SUCCEEDED proof and runtime registration pending; no full P03/Gate claim.')


if __name__ == '__main__':
    fixture.verify(exercise=exercise)
