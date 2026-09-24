"""Atomic ciphertext-only Secret create/rotate persistence."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.secret_access import (
    EncryptedSecretDraft, SecretConsumer, SecretPurpose, SecretRef,
)
from plm_assistant.modules.platform.infrastructure.secret_orm import SecretRecordRow, SecretVersionRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Secret write transaction is required")
    return session


def _metadata(draft: EncryptedSecretDraft) -> dict[str, str]:
    data = json.loads(draft.encryption_metadata)
    if type(data) is not dict or set(data) != {"algorithm", "nonce"}:
        raise RuntimeError("invalid Secret ciphertext metadata")
    return data


class SqlAlchemySecretWriteRepository:
    def create(self, transaction: object, *, secret_ref: SecretRef,
               purpose: SecretPurpose, consumer: SecretConsumer,
               encrypted: EncryptedSecretDraft, actor: uuid.UUID) -> uuid.UUID:
        session = _session(transaction)
        record = SecretRecordRow(
            secret_record_id=secret_ref.secret_id, purpose=purpose.value,
            allowed_consumer=consumer.value, created_by=actor,
        )
        session.add(record)
        session.flush()
        version = SecretVersionRow(
            secret_record_id=secret_ref.secret_id, version_no=1,
            encrypted_payload=encrypted.encrypted_payload,
            encryption_metadata=_metadata(encrypted),
            key_provider_ref=encrypted.key_provider_ref, created_by=actor,
        )
        session.add(version)
        session.flush()
        session.execute(update(SecretVersionRow).where(
            SecretVersionRow.secret_version_id == version.secret_version_id,
        ).values(activated_at=select_now()))
        session.execute(update(SecretRecordRow).where(
            SecretRecordRow.secret_record_id == secret_ref.secret_id,
            SecretRecordRow.lock_version == 0,
        ).values(secret_state="ACTIVE", current_version_ref=version.secret_version_id,
                 lock_version=1, updated_at=select_now()))
        return version.secret_version_id

    def lock_current(self, transaction: object, *, secret_ref: SecretRef,
                     expected_version_no: int) -> tuple[SecretPurpose, SecretConsumer] | None:
        session = _session(transaction)
        row = session.execute(select(SecretRecordRow, SecretVersionRow).join(
            SecretVersionRow,
            SecretRecordRow.current_version_ref == SecretVersionRow.secret_version_id,
        ).where(
            SecretRecordRow.secret_record_id == secret_ref.secret_id,
            SecretRecordRow.secret_state == "ACTIVE",
            SecretVersionRow.secret_record_id == secret_ref.secret_id,
            SecretVersionRow.version_no == expected_version_no,
            SecretVersionRow.activated_at.is_not(None),
            SecretVersionRow.retired_at.is_(None),
        ).with_for_update(of=SecretRecordRow)).one_or_none()
        if row is None:
            return None
        record, _ = row
        return SecretPurpose(record.purpose), SecretConsumer(record.allowed_consumer)

    def rotate(self, transaction: object, *, secret_ref: SecretRef,
               expected_version_no: int, encrypted: EncryptedSecretDraft,
               actor: uuid.UUID) -> uuid.UUID:
        session = _session(transaction)
        record = session.execute(select(SecretRecordRow).where(
            SecretRecordRow.secret_record_id == secret_ref.secret_id,
            SecretRecordRow.secret_state == "ACTIVE",
        ).with_for_update()).scalar_one_or_none()
        if record is None or record.current_version_ref is None:
            raise RuntimeError("Secret version conflict")
        old = session.execute(select(SecretVersionRow).where(
            SecretVersionRow.secret_version_id == record.current_version_ref,
            SecretVersionRow.secret_record_id == record.secret_record_id,
            SecretVersionRow.version_no == expected_version_no,
            SecretVersionRow.activated_at.is_not(None),
            SecretVersionRow.retired_at.is_(None),
        )).scalar_one_or_none()
        if old is None:
            raise RuntimeError("Secret version conflict")
        new = SecretVersionRow(
            secret_record_id=record.secret_record_id, version_no=expected_version_no + 1,
            encrypted_payload=encrypted.encrypted_payload,
            encryption_metadata=_metadata(encrypted),
            key_provider_ref=encrypted.key_provider_ref, created_by=actor,
        )
        session.add(new)
        session.flush()
        now = select_now()
        session.execute(update(SecretVersionRow).where(
            SecretVersionRow.secret_version_id == old.secret_version_id,
        ).values(retired_at=now))
        session.execute(update(SecretVersionRow).where(
            SecretVersionRow.secret_version_id == new.secret_version_id,
        ).values(activated_at=now))
        session.execute(update(SecretRecordRow).where(
            SecretRecordRow.secret_record_id == record.secret_record_id,
            SecretRecordRow.lock_version == record.lock_version,
        ).values(current_version_ref=new.secret_version_id,
                 lock_version=record.lock_version + 1, updated_at=now))
        return new.secret_version_id


def select_now():
    return func.statement_timestamp()
