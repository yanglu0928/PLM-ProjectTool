"""Document-owned first ParseRecord: trigger-legal PENDING -> RUNNING."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError, ReconciledParseAttempt,
    StartedParseAttempt,
)
from plm_assistant.modules.jobs.application.lease import ClosedJobAttempt
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

    def start_retry(self, tx: object, *, job_id: uuid.UUID,
                    request: DocumentParseAttemptRequest, scope: str,
                    project_id: uuid.UUID | None, attempt_no: int,
                    closed: tuple[ClosedJobAttempt, ...]
                    ) -> tuple[StartedParseAttempt, tuple[ReconciledParseAttempt, ...]]:
        try:
            if (type(request) is not DocumentParseAttemptRequest
                    or type(job_id) is not uuid.UUID or job_id.int == 0
                    or type(attempt_no) is not int or attempt_no not in (2, 3)
                    or type(closed) is not tuple or len(closed) != attempt_no - 1
                    or any(type(item) is not ClosedJobAttempt
                           for item in closed)):
                raise ParseAttemptError("VALIDATION_FAILED")
            request.__post_init__()
            if [item.attempt_no for item in closed] != list(range(1, attempt_no)):
                raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
            session = tx.session
            if not isinstance(session, Session) or not session.in_transaction():
                raise ParseAttemptError()
            version = session.scalar(select(DocumentVersionRow).where(
                DocumentVersionRow.document_version_id == request.document_version_id)
                .with_for_update(of=DocumentVersionRow)
                .execution_options(populate_existing=True))
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
                .order_by(ParseRecordRow.attempt_no)
                .with_for_update(of=ParseRecordRow)
                .execution_options(populate_existing=True)).all()
            if (len(records) > attempt_no
                    or any(row.job_ref != job_id or row.attempt_no != index
                           for index, row in enumerate(records, start=1))):
                raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
            changed: list[ReconciledParseAttempt] = []
            for prior in closed:
                row = records[prior.attempt_no - 1] if len(records) >= prior.attempt_no else None
                if row is None:
                    row = ParseRecordRow(document_version_id=request.document_version_id,
                        scope=scope, project_id=project_id,
                        parser_profile=request.parser_profile,
                        parser_version=request.parser_version,
                        job_ref=job_id, attempt_no=prior.attempt_no,
                        parse_state="PENDING", lock_version=0)
                    session.add(row)
                    session.flush()
                    row.parse_state = "CANCELLED"
                    row.completed_at = session.scalar(select(func.clock_timestamp()))
                    row.retryable = False
                    row.lock_version = 1
                    session.flush()
                    changed.append(ReconciledParseAttempt(
                        row.parse_record_id, row.attempt_no, "PENDING", "CANCELLED"))
                    records.append(row)
                elif row.parse_state == "RUNNING":
                    if (row.started_at is None or row.started_at > prior.completed_at
                            or row.completed_at is not None or row.result_ref is not None
                            or row.result_sha256 is not None or row.error_code is not None
                            or row.retryable is not None or row.lock_version != 1):
                        raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
                    row.parse_state = "FAILED"
                    row.completed_at = prior.completed_at
                    row.error_code = prior.error_code
                    row.retryable = True
                    row.lock_version = 2
                    session.flush()
                    changed.append(ReconciledParseAttempt(
                        row.parse_record_id, row.attempt_no, "RUNNING", "FAILED"))
                elif row.parse_state == "PENDING":
                    if (row.started_at is not None or row.completed_at is not None
                            or row.lock_version != 0):
                        raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
                    row.parse_state = "CANCELLED"
                    row.completed_at = session.scalar(select(func.clock_timestamp()))
                    row.retryable = False
                    row.lock_version = 1
                    session.flush()
                    changed.append(ReconciledParseAttempt(
                        row.parse_record_id, row.attempt_no, "PENDING", "CANCELLED"))
                elif row.parse_state == "FAILED":
                    if (row.error_code != prior.error_code or row.completed_at is None
                            or row.started_at is None
                            or not row.started_at <= row.completed_at <= prior.completed_at
                            or row.retryable is not True or row.lock_version != 2
                            or row.result_ref is not None or row.result_sha256 is not None):
                        raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
                elif row.parse_state == "CANCELLED":
                    if (row.completed_at is None or row.retryable is not False
                            or row.lock_version != 1):
                        raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
                else:
                    raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
            if len(records) == attempt_no:
                current = records[-1]
                if (current.parse_state != "RUNNING" or current.started_at is None
                        or current.completed_at is not None or current.lock_version != 1):
                    raise ParseAttemptError("PARSER_ATTEMPT_CONFLICT")
            else:
                current = ParseRecordRow(document_version_id=request.document_version_id,
                    scope=scope, project_id=project_id,
                    parser_profile=request.parser_profile,
                    parser_version=request.parser_version,
                    job_ref=job_id, attempt_no=attempt_no,
                    parse_state="PENDING", lock_version=0)
                session.add(current)
                session.flush()
                current.parse_state = "RUNNING"
                current.started_at = session.scalar(select(func.clock_timestamp()))
                current.lock_version = 1
                session.flush()
            return self._result(current), tuple(changed)
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
