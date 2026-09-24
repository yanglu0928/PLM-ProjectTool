"""Read an active encrypted Secret envelope for the existing one-call resolver."""

from __future__ import annotations

import json
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretState,
)
from plm_assistant.modules.platform.infrastructure.secret_orm import SecretRecordRow, SecretVersionRow


class SqlAlchemyEncryptedSecretStore:
    def __init__(self, unit_of_work: Callable[[], object]) -> None:
        if unit_of_work is None:
            raise ValueError("secret store transaction factory is required")
        self._unit_of_work = unit_of_work

    def load(self, secret_ref: SecretRef) -> SecretEnvelope | None:
        if not isinstance(secret_ref, SecretRef):
            return None
        with self._unit_of_work() as tx:
            session = tx.session  # type: ignore[attr-defined]
            if not isinstance(session, Session) or not session.in_transaction():
                raise RuntimeError("active secret read transaction is required")
            row = session.execute(select(SecretRecordRow, SecretVersionRow).join(
                SecretVersionRow,
                SecretRecordRow.current_version_ref == SecretVersionRow.secret_version_id,
            ).where(
                SecretRecordRow.secret_record_id == secret_ref.secret_id,
                SecretRecordRow.secret_state == "ACTIVE",
                SecretVersionRow.secret_record_id == secret_ref.secret_id,
                SecretVersionRow.activated_at.is_not(None),
                SecretVersionRow.retired_at.is_(None),
            )).one_or_none()
            if row is None:
                return None
            record, version = row
            try:
                purpose = SecretPurpose(record.purpose)
                consumer = SecretConsumer(record.allowed_consumer)
                if (type(version.encryption_metadata) is not dict
                        or type(version.encrypted_payload) is not bytes
                        or not version.encrypted_payload
                        or type(version.version_no) is not int or version.version_no < 1):
                    return None
                metadata = json.dumps(version.encryption_metadata, ensure_ascii=False,
                                      sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode("utf-8")
                return SecretEnvelope(
                    secret_ref=secret_ref, purpose=purpose, state=SecretState.ACTIVE,
                    allowed_consumer=consumer, version_no=version.version_no,
                    encrypted_payload=version.encrypted_payload,
                    encryption_metadata=metadata,
                    key_provider_ref=version.key_provider_ref,
                )
            except (TypeError, ValueError, UnicodeError):
                return None
