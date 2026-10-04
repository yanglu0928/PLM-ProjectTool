"""Document-only tables, no Jobs private access and no result physical path exposure."""
from sqlalchemy import select
from .read_repository import _session
from .orm import ParseRecordRow, ParseResultRefRow
from ..application.parse_job_result import ParseJobResultSource
from plm_assistant.modules.jobs.application.authorized_read import JobReadError


class SqlAlchemyDocumentParseJobResults:
    def get(self, tx, *, job_id):
        session = _session(tx)
        records = session.scalars(select(ParseRecordRow).where(ParseRecordRow.job_ref == job_id,
            ParseRecordRow.parse_state == 'SUCCEEDED').limit(2)
            .with_for_update(read=True, of=ParseRecordRow).execution_options(populate_existing=True)).all()
        if len(records) != 1: raise JobReadError()
        row = records[0]
        result = session.scalar(select(ParseResultRefRow).where(ParseResultRefRow.parse_result_ref_id == row.result_ref,
            ParseResultRefRow.parse_record_id == row.parse_record_id))
        if (result is None or result.sha256 != row.result_sha256 or row.error_code is not None or row.retryable is not False
            or type(row.attempt_no) is not int or row.attempt_no < 1
            or type(result.result_schema_version) is not int or result.result_schema_version < 1
            or type(result.size_bytes) is not int or result.size_bytes < 0):
            raise JobReadError()
        return ParseJobResultSource(row.parse_record_id, row.job_ref, row.document_version_id, row.scope, row.project_id,
            result.parse_result_ref_id, result.sha256, row.created_at, row.started_at, row.completed_at, result.created_at)
