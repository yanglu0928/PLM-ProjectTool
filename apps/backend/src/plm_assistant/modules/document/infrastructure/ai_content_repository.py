"""Locked PostgreSQL facts for Document AI content selection and reread."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select

from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentSource,
)

from .orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow, ParseRecordRow,
    ParseResultRefRow,
)
from .read_repository import _session


class SqlAlchemyDocumentAIContentRepository:
    def select_current(
        self, transaction: object, *, project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
        allowed_parser_versions: frozenset[tuple[str, str]],
        max_result_bytes: int,
    ) -> DocumentAIContentSource | None:
        parser_filter = or_(*(
            and_(ParseRecordRow.parser_profile == profile,
                 ParseRecordRow.parser_version == version)
            for profile, version in sorted(allowed_parser_versions)
        ))
        statement = self._base(
            project_id=project_id, document_id=document_id,
            document_version_id=document_version_id,
        ).where(
            parser_filter,
            ParseResultRefRow.size_bytes.between(1, max_result_bytes),
        ).order_by(
            ParseRecordRow.completed_at.desc(),
            ParseRecordRow.parse_record_id.desc(),
        ).limit(1)
        row = _session(transaction).execute(
            self._locked(statement)).one_or_none()
        return None if row is None else self._source(row)

    def get_exact(
        self, transaction: object, *, project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
        parse_record_id: uuid.UUID, result_ref_id: uuid.UUID,
    ) -> DocumentAIContentSource | None:
        statement = self._base(
            project_id=project_id, document_id=document_id,
            document_version_id=document_version_id,
        ).where(
            ParseRecordRow.parse_record_id == parse_record_id,
            ParseResultRefRow.parse_result_ref_id == result_ref_id,
        )
        row = _session(transaction).execute(
            self._locked(statement)).one_or_none()
        return None if row is None else self._source(row)

    @staticmethod
    def _base(*, project_id: uuid.UUID, document_id: uuid.UUID,
              document_version_id: uuid.UUID):
        return select(
            DocumentRow, DocumentVersionRow, FileObjectRow,
            ParseRecordRow, ParseResultRefRow,
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_id == DocumentRow.document_id,
        ).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).join(
            ParseRecordRow,
            ParseRecordRow.document_version_id
            == DocumentVersionRow.document_version_id,
        ).join(
            ParseResultRefRow,
            ParseResultRefRow.parse_record_id == ParseRecordRow.parse_record_id,
        ).where(
            DocumentRow.document_id == document_id,
            DocumentRow.scope == "PROJECT",
            DocumentRow.project_id == project_id,
            DocumentRow.document_state.in_(("ACTIVE", "ARCHIVED")),
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentVersionRow.scope == "PROJECT",
            DocumentVersionRow.project_id == project_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            FileObjectRow.scope == "PROJECT",
            FileObjectRow.project_id == project_id,
            FileObjectRow.usage_kind == "DOCUMENT",
            FileObjectRow.owner_object_id.is_(None),
            FileObjectRow.storage_class == "PERSISTENT",
            FileObjectRow.file_state == "AVAILABLE",
            FileObjectRow.sha256 == DocumentVersionRow.content_sha256,
            FileObjectRow.size_bytes == DocumentVersionRow.size_bytes,
            FileObjectRow.detected_mime == DocumentVersionRow.detected_mime,
            ParseRecordRow.scope == "PROJECT",
            ParseRecordRow.project_id == project_id,
            ParseRecordRow.parse_state == "SUCCEEDED",
            ParseRecordRow.result_ref == ParseResultRefRow.parse_result_ref_id,
            ParseRecordRow.result_sha256 == ParseResultRefRow.sha256,
            ParseRecordRow.error_code.is_(None),
            ParseRecordRow.retryable.is_(False),
            ParseResultRefRow.result_schema_version == 1,
        )

    @staticmethod
    def _locked(statement):
        return statement.with_for_update(
            read=True,
            of=(DocumentRow, DocumentVersionRow, FileObjectRow,
                ParseRecordRow, ParseResultRefRow),
        ).execution_options(populate_existing=True)

    @staticmethod
    def _source(row: object) -> DocumentAIContentSource:
        document, version, _file, record, result = row
        return DocumentAIContentSource(
            document.document_id, version.document_version_id,
            document.project_id, record.parse_record_id,
            result.parse_result_ref_id, record.parser_profile,
            record.parser_version, result.storage_locator,
            version.content_sha256, result.sha256, result.size_bytes,
            result.result_schema_version,
        )
