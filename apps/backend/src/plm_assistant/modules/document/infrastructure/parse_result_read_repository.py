"""Private fixed ParseRecord/ResultRef facts for Document's read Port."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.document.application.read_parse_result import FixedParseResultSource

from .orm import ParseRecordRow, ParseResultRefRow
from .read_repository import _session


class SqlAlchemyParseResultReadRepository:
    def get(self, transaction: object, *, scope: str, project_id: uuid.UUID | None,
            document_version_id: uuid.UUID,
            parse_record_id: uuid.UUID) -> FixedParseResultSource | None:
        pair = _session(transaction).execute(
            select(ParseRecordRow, ParseResultRefRow).join(
                ParseResultRefRow,
                ParseResultRefRow.parse_record_id == ParseRecordRow.parse_record_id,
            ).where(
                ParseRecordRow.parse_record_id == parse_record_id,
                ParseRecordRow.document_version_id == document_version_id,
                ParseRecordRow.scope == scope,
                ParseRecordRow.project_id == project_id,
                ParseRecordRow.parse_state == "SUCCEEDED",
                ParseRecordRow.result_ref == ParseResultRefRow.parse_result_ref_id,
                ParseRecordRow.result_sha256 == ParseResultRefRow.sha256,
                ParseRecordRow.error_code.is_(None),
                ParseRecordRow.retryable.is_(False),
            ),
        ).one_or_none()
        if pair is None:
            return None
        record, result = pair
        return FixedParseResultSource(
            record.parse_record_id, record.document_version_id,
            record.scope, record.project_id,
            record.parser_profile, record.parser_version,
            result.parse_result_ref_id, result.storage_locator,
            result.sha256, result.size_bytes, result.result_schema_version,
        )
