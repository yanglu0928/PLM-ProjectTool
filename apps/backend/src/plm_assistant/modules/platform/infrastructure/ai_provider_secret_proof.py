"""Platform-owned current Secret metadata proof for an AI Provider config."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.infrastructure.secret_orm import (
    SecretRecordRow, SecretVersionRow,
)


class SqlAlchemyAIProviderSecretProof:
    def active_provider_key(self, transaction: object, *, secret_ref: uuid.UUID) -> bool:
        if type(secret_ref) is not uuid.UUID or secret_ref.int == 0:
            return False
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Secret proof transaction is required")
        record = session.execute(select(
            SecretRecordRow.secret_record_id, SecretRecordRow.current_version_ref,
        ).where(
            SecretRecordRow.secret_record_id == secret_ref,
            SecretRecordRow.purpose == "AI_PROVIDER_KEY",
            SecretRecordRow.allowed_consumer == "AI_PROVIDER_ADAPTER",
            SecretRecordRow.secret_state == "ACTIVE",
            SecretRecordRow.current_version_ref.is_not(None),
        ).with_for_update(of=SecretRecordRow)).one_or_none()
        if record is None:
            return False
        return session.execute(select(SecretVersionRow.secret_version_id).where(
            SecretVersionRow.secret_version_id == record.current_version_ref,
            SecretVersionRow.secret_record_id == record.secret_record_id,
            SecretVersionRow.activated_at.is_not(None),
            SecretVersionRow.retired_at.is_(None),
        )).scalar_one_or_none() is not None
