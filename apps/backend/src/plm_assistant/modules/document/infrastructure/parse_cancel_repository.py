"""Cancel only a current RUNNING ParseRecord under the caller's Job lock."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_cancel import (
    CancelledParseAttempt, ParseCancelError, ParseCancelRequest,
)
from .orm import ParseRecordRow


class SqlAlchemyParseCancelRepository:
    def verified_cancelled_current(self, tx: object, *, request: ParseCancelRequest
                                   ) -> CancelledParseAttempt | None:
        """Read-only proof: absence is legal, but a present row must be exact terminal."""
        try:
            if type(request) is not ParseCancelRequest or request.started is not None:
                raise ParseCancelError("VALIDATION_FAILED")
            request.__post_init__()
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParseCancelError()
            rows = session.scalars(select(ParseRecordRow).where(
                ParseRecordRow.job_ref == request.job_id,
                ParseRecordRow.attempt_no == request.attempt_no)).all()
            if not rows:
                return None
            if len(rows) != 1:
                raise ParseCancelError()
            row = rows[0]
            if (row.parse_state != "CANCELLED" or row.lock_version != 2
                    or row.started_at is None or row.completed_at is None
                    or row.result_ref is not None or row.result_sha256 is not None
                    or row.error_code != "JOB_CANCELLED" or row.retryable is not False
                    or (row.document_version_id, row.scope, row.project_id)
                    != (request.document_version_id, request.scope, request.project_id)):
                raise ParseCancelError()
            return CancelledParseAttempt(row.parse_record_id, row.completed_at)
        except ParseCancelError:
            raise
        except Exception:
            raise ParseCancelError() from None

    def cancel_current(self, tx: object, *, request: ParseCancelRequest
                       ) -> CancelledParseAttempt | None:
        try:
            if type(request) is not ParseCancelRequest:
                raise ParseCancelError("VALIDATION_FAILED")
            request.__post_init__()
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParseCancelError()
            rows = session.scalars(select(ParseRecordRow).where(
                ParseRecordRow.job_ref == request.job_id,
                ParseRecordRow.attempt_no == request.attempt_no)
                .with_for_update(of=ParseRecordRow)
                .execution_options(populate_existing=True)).all()
            if not rows:
                if request.started is not None:
                    raise ParseCancelError()
                return None
            if len(rows) != 1:
                raise ParseCancelError()
            row = rows[0]
            if (row.parse_state != "RUNNING" or row.lock_version != 1
                    or row.started_at is None or row.completed_at is not None
                    or row.result_ref is not None or row.result_sha256 is not None
                    or row.error_code is not None or row.retryable is not None
                    or (row.document_version_id, row.scope, row.project_id)
                    != (request.document_version_id, request.scope, request.project_id)):
                raise ParseCancelError()
            if request.started is not None and (
                    row.parse_record_id != request.started.parse_record_id
                    or row.started_at != request.started.started_at
                    or row.parser_profile != request.started.parser_profile
                    or row.parser_version != request.started.parser_version):
                raise ParseCancelError()
            completed = session.scalar(select(func.clock_timestamp()))
            row.parse_state = "CANCELLED"
            row.completed_at = completed
            row.error_code = "JOB_CANCELLED"
            row.retryable = False
            row.lock_version = 2
            session.flush()
            return CancelledParseAttempt(row.parse_record_id, completed)
        except ParseCancelError:
            raise
        except Exception:
            raise ParseCancelError() from None
