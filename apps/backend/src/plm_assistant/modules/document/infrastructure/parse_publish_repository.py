"""Document-owned result reference and ParseRecord success in caller transaction."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_publish import (
    ParsePublishError, ParseSuccessRequest, PublishedParseResult,
)
from .orm import ParseRecordRow, ParseResultRefRow


class SqlAlchemyParsePublishRepository:
    def publish_success(self, tx: object, *, request: ParseSuccessRequest
                        ) -> PublishedParseResult:
        try:
            if type(request) is not ParseSuccessRequest:
                raise ParsePublishError("VALIDATION_FAILED")
            request.__post_init__()
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParsePublishError()
            row = session.scalar(select(ParseRecordRow).where(
                ParseRecordRow.parse_record_id == request.parse_record_id)
                .with_for_update(of=ParseRecordRow)
                .execution_options(populate_existing=True))
            if (row is None or row.parse_state != "RUNNING" or row.lock_version != 1
                    or row.started_at is None or row.completed_at is not None
                    or row.result_ref is not None or row.result_sha256 is not None
                    or row.error_code is not None or row.retryable is not None
                    or (row.job_ref, row.document_version_id, row.scope, row.project_id,
                        row.parser_profile, row.parser_version, row.attempt_no)
                    != (request.job_id, request.document_version_id,
                        request.scope, request.project_id, request.parser_profile,
                        request.parser_version, request.attempt_no)):
                raise ParsePublishError("PARSER_ATTEMPT_CONFLICT")
            file = request.file
            session.add(ParseResultRefRow(
                parse_result_ref_id=file.result_ref_id,
                parse_record_id=row.parse_record_id,
                storage_locator=file.storage_locator,
                result_schema_version=1,
                sha256=file.sha256,
                size_bytes=file.size_bytes,
            ))
            session.flush()
            row.parse_state = "SUCCEEDED"
            row.result_ref = file.result_ref_id
            row.result_sha256 = file.sha256
            row.completed_at = session.scalar(select(func.clock_timestamp()))
            row.retryable = False
            row.lock_version = 2
            session.flush()
            return PublishedParseResult(row.parse_record_id, file.result_ref_id,
                                        row.completed_at)
        except ParsePublishError:
            raise
        except Exception:
            raise ParsePublishError() from None
