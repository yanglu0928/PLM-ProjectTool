"""Document-owned first ParseRecord: trigger-legal PENDING -> RUNNING."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError, StartedParseAttempt,
)
from .orm import DocumentVersionRow, ParseRecordRow


class SqlAlchemyParseAttemptRepository:
    def start_first(self, tx: object, *, job_id: uuid.UUID,
                    request: DocumentParseAttemptRequest,
                    scope: str, project_id: uuid.UUID | None) -> StartedParseAttempt:
        try:
            if type(request) is not DocumentParseAttemptRequest:
                raise ParseAttemptError()
            request.__post_init__()
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParseAttemptError()
            version = session.scalar(select(DocumentVersionRow).where(
                DocumentVersionRow.document_version_id == request.document_version_id)
                .with_for_update(of=DocumentVersionRow).execution_options(populate_existing=True))
            if (version is None or version.availability_state != "AVAILABLE"
                    or (version.scope, version.project_id, version.content_sha256,
                        version.size_bytes, version.detected_mime)
                    != (scope, project_id, request.content_sha256,
                        request.size_bytes, request.detected_mime)):
                raise ParseAttemptError()
            records = session.scalars(select(ParseRecordRow).where(
                ParseRecordRow.document_version_id == request.document_version_id,
                ParseRecordRow.parser_profile == request.parser_profile,
                ParseRecordRow.parser_version == request.parser_version)
                .with_for_update(of=ParseRecordRow)
                .execution_options(populate_existing=True)).all()
            if records:
                if (len(records) != 1 or records[0].job_ref != job_id
                        or records[0].attempt_no != 1
                        or records[0].parse_state != "RUNNING"):
                    raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
                return self._result(records[0])
            row = ParseRecordRow(document_version_id=request.document_version_id,
                scope=scope, project_id=project_id, parser_profile=request.parser_profile,
                parser_version=request.parser_version, job_ref=job_id, attempt_no=1,
                parse_state="PENDING", lock_version=0)
            session.add(row)
            session.flush()
            row.parse_state = "RUNNING"
            row.started_at = session.scalar(select(func.statement_timestamp()))
            row.lock_version = 1
            session.flush()
            return self._result(row)
        except ParseAttemptError:
            raise
        except Exception:
            raise ParseAttemptError() from None

    @staticmethod
    def _result(row: ParseRecordRow) -> StartedParseAttempt:
        if row.started_at is None:
            raise ParseAttemptError()
        return StartedParseAttempt(row.parse_record_id, row.job_ref,
            row.document_version_id, row.parser_profile, row.parser_version,
            row.attempt_no, row.started_at)
