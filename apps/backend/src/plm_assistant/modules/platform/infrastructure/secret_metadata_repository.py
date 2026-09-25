"""Safe Secret metadata projection; never select ciphertext or key reference."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.secret_metadata import SecretMetadataView
from plm_assistant.modules.platform.infrastructure.secret_orm import SecretRecordRow, SecretVersionRow


_FIELDS = (
    SecretRecordRow.secret_record_id, SecretRecordRow.purpose,
    SecretRecordRow.secret_state, SecretRecordRow.allowed_consumer,
    SecretVersionRow.version_no, SecretRecordRow.created_at, SecretRecordRow.updated_at,
    SecretRecordRow.lock_version,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active secret metadata transaction is required")
    return session


def _view(row: object) -> SecretMetadataView:
    return SecretMetadataView(*row)


class SqlAlchemySecretMetadataRepository:
    def get(self, transaction: object, secret_id: uuid.UUID) -> SecretMetadataView | None:
        row = _session(transaction).execute(select(*_FIELDS).select_from(SecretRecordRow).outerjoin(
            SecretVersionRow,
            (SecretRecordRow.current_version_ref == SecretVersionRow.secret_version_id)
            & (SecretRecordRow.secret_record_id == SecretVersionRow.secret_record_id),
        ).where(SecretRecordRow.secret_record_id == secret_id)).one_or_none()
        return _view(row) if row is not None else None

    def list_page(self, transaction: object, *, after: uuid.UUID | None,
                  limit: int) -> list[SecretMetadataView]:
        statement = select(*_FIELDS).select_from(SecretRecordRow).outerjoin(
            SecretVersionRow,
            (SecretRecordRow.current_version_ref == SecretVersionRow.secret_version_id)
            & (SecretRecordRow.secret_record_id == SecretVersionRow.secret_record_id),
        )
        if after is not None:
            statement = statement.where(SecretRecordRow.secret_record_id > after)
        rows = _session(transaction).execute(statement.order_by(
            SecretRecordRow.secret_record_id,
        ).limit(limit)).all()
        return [_view(row) for row in rows]
