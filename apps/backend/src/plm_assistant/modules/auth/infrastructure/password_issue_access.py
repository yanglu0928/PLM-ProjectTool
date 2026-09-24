"""Real password proof check for internal Session issuance only."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.ports.password_verify import PasswordVerifierPort
from plm_assistant.modules.auth.application.session_service import PasswordIssueProof
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordCredentialRow, UserRow


class SqlAlchemyPasswordIssueAccess:
    def __init__(self, verifier: PasswordVerifierPort) -> None:
        if verifier is None:
            raise ValueError("password verifier is required")
        self._verifier = verifier

    def can_issue(self, transaction: object, user_id: uuid.UUID,
                  credential_version: int, proof: object) -> bool:
        if (type(proof) is not PasswordIssueProof or type(proof.password) is not bytearray
                or not 1 <= len(proof.password) <= 1024):
            return False
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise RuntimeError("active auth transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active auth transaction is required")
        row = session.execute(
            select(PasswordCredentialRow.password_hash,
                   PasswordCredentialRow.algorithm_id,
                   PasswordCredentialRow.parameter_set)
            .select_from(UserRow)
            .join(PasswordCredentialRow,
                  UserRow.active_password_credential_id == PasswordCredentialRow.password_credential_id)
            .where(UserRow.user_id == user_id,
                   UserRow.state == "ENABLED",
                   UserRow.credential_version == credential_version,
                   PasswordCredentialRow.user_id == user_id,
                   PasswordCredentialRow.credential_version == credential_version)
        ).one_or_none()
        if row is None:
            return False
        password = memoryview(proof.password)
        try:
            return self._verifier.verify_password(
                password, password_hash=row.password_hash,
                algorithm_id=row.algorithm_id, parameter_set=row.parameter_set,
            ) is True
        finally:
            password.release()
