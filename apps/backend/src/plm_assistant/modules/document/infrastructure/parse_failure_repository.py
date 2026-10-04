"""Lock and fail one current Document ParseRecord within the caller's UOW."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_failure import (
    FailedParseAttempt, ParseFailureError, ParseFailureRequest,
)
from .orm import ParseRecordRow


class SqlAlchemyParseFailureRepository:
    def fail_started(self, tx: object, *, request: ParseFailureRequest) -> FailedParseAttempt:
        try:
            if type(request) is not ParseFailureRequest:
                raise ParseFailureError("VALIDATION_FAILED")
            request.__post_init__()
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParseFailureError()
            started = request.started
            row = session.scalar(select(ParseRecordRow).where(
                ParseRecordRow.parse_record_id == started.parse_record_id)
                .with_for_update(of=ParseRecordRow)
                .execution_options(populate_existing=True))
            if (row is None or row.parse_state != "RUNNING" or row.lock_version != 1
                    or row.started_at != started.started_at
                    or row.completed_at is not None or row.result_ref is not None
                    or row.result_sha256 is not None or row.error_code is not None
                    or row.retryable is not None
                    or (row.job_ref, row.document_version_id, row.scope, row.project_id,
                        row.parser_profile, row.parser_version, row.attempt_no)
                    != (started.job_id, started.document_version_id,
                        request.scope, request.project_id, started.parser_profile,
                        started.parser_version, started.attempt_no)):
                raise ParseFailureError()
            completed = session.scalar(select(func.clock_timestamp()))
            row.parse_state = "FAILED"
            row.completed_at = completed
            row.error_code = request.error_code
            row.retryable = request.retryable
            row.lock_version = 2
            session.flush()
            return FailedParseAttempt(started.parse_record_id, completed)
        except ParseFailureError:
            raise
        except Exception:
            raise ParseFailureError() from None
