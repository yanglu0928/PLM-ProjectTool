"""Transactional PostgreSQL reservation and immutable replay lookup."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.idempotency_orm import IdempotencyReceiptRow


class SqlAlchemyIdempotencyReceipts:
    """Reserve and complete inside the caller's business/Audit transaction."""

    def lookup_result(self, uow: SqlAlchemyUnitOfWork, *, scope: IdempotencyScope) -> IdempotencyResult | None:
        """Read a completed result for an already authorized actor-scoped operation.

        Absence is inconclusive: another transaction may still be committing.
        This method never reserves, locks, flushes or commits. The caller must
        prove current Session/role/resource ownership before invoking it.
        """
        if type(scope) is not IdempotencyScope:
            raise IdempotencyError("VALIDATION_FAILED")
        scope.__post_init__()
        try:
            row = uow.session.execute(
                select(
                    IdempotencyReceiptRow.state,
                    IdempotencyReceiptRow.result_ref_type,
                    IdempotencyReceiptRow.result_ref_id,
                    IdempotencyReceiptRow.result_status,
                ).where(
                    IdempotencyReceiptRow.actor_id == scope.actor_id,
                    IdempotencyReceiptRow.project_id == scope.project_id,
                    IdempotencyReceiptRow.operation == scope.operation,
                    IdempotencyReceiptRow.key_digest == scope.key_digest,
                ).execution_options(autoflush=False)
            ).one_or_none()
        except SQLAlchemyError:
            raise IdempotencyError("SYSTEM_UNAVAILABLE") from None
        if row is None:
            return None
        if row[0] != "COMPLETED":
            raise IdempotencyError("SYSTEM_UNAVAILABLE")
        try:
            return IdempotencyResult(row[1], row[2], row[3])
        except IdempotencyError:
            raise IdempotencyError("SYSTEM_UNAVAILABLE") from None

    def lookup_completed(self, uow: SqlAlchemyUnitOfWork, *, scope: IdempotencyScope,
                         request_fingerprint: bytes) -> IdempotencyResult | None:
        """Read a hint only; caller must recheck authority and reserve atomically.

        A missing receipt is not permission to write. No row lock, autoflush or
        commit is performed; scalar projection avoids cached ORM entity state.
        """
        if (type(scope) is not IdempotencyScope or type(request_fingerprint) is not bytes
                or len(request_fingerprint) != 32):
            raise IdempotencyError("VALIDATION_FAILED")
        scope.__post_init__()
        try:
            row = uow.session.execute(
                select(
                    IdempotencyReceiptRow.state,
                    IdempotencyReceiptRow.request_fingerprint,
                    IdempotencyReceiptRow.result_ref_type,
                    IdempotencyReceiptRow.result_ref_id,
                    IdempotencyReceiptRow.result_status,
                ).where(
                    IdempotencyReceiptRow.actor_id == scope.actor_id,
                    IdempotencyReceiptRow.project_id == scope.project_id,
                    IdempotencyReceiptRow.operation == scope.operation,
                    IdempotencyReceiptRow.key_digest == scope.key_digest,
                ).execution_options(autoflush=False)
            ).one_or_none()
        except SQLAlchemyError:
            raise IdempotencyError("SYSTEM_UNAVAILABLE") from None
        if row is None:
            return None
        if row[0] != "COMPLETED" or type(row[1]) is not bytes or len(row[1]) != 32:
            raise IdempotencyError("SYSTEM_UNAVAILABLE")
        if row[1] != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        try:
            return IdempotencyResult(row[2], row[3], row[4])
        except IdempotencyError:
            raise IdempotencyError("SYSTEM_UNAVAILABLE") from None

    def reserve(self, uow: SqlAlchemyUnitOfWork, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None:
        if (type(scope) is not IdempotencyScope or type(request_fingerprint) is not bytes
                or len(request_fingerprint) != 32):
            raise IdempotencyError("VALIDATION_FAILED")
        inserted = uow.session.execute(
            pg_insert(IdempotencyReceiptRow).values(
                actor_id=scope.actor_id, project_id=scope.project_id,
                operation=scope.operation, key_digest=scope.key_digest,
                request_fingerprint=request_fingerprint, state="PENDING",
            ).on_conflict_do_nothing(
                constraint="uq_plt_idem_receipts__scope"
            ).returning(IdempotencyReceiptRow.receipt_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return None
        row = uow.session.execute(
            select(IdempotencyReceiptRow).where(
                IdempotencyReceiptRow.actor_id == scope.actor_id,
                IdempotencyReceiptRow.project_id == scope.project_id,
                IdempotencyReceiptRow.operation == scope.operation,
                IdempotencyReceiptRow.key_digest == scope.key_digest,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None or row.state != "COMPLETED":
            raise IdempotencyError("SYSTEM_UNAVAILABLE")
        if row.request_fingerprint != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        if row.result_ref_type is None or row.result_ref_id is None or row.result_status is None:
            raise IdempotencyError("SYSTEM_UNAVAILABLE")
        return IdempotencyResult(row.result_ref_type, row.result_ref_id, row.result_status)

    def complete(self, uow: SqlAlchemyUnitOfWork, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None:
        if type(scope) is not IdempotencyScope or type(result) is not IdempotencyResult:
            raise IdempotencyError("VALIDATION_FAILED")
        changed = uow.session.execute(
            update(IdempotencyReceiptRow).where(
                IdempotencyReceiptRow.actor_id == scope.actor_id,
                IdempotencyReceiptRow.project_id == scope.project_id,
                IdempotencyReceiptRow.operation == scope.operation,
                IdempotencyReceiptRow.key_digest == scope.key_digest,
                IdempotencyReceiptRow.state == "PENDING",
            ).values(
                state="COMPLETED", result_ref_type=result.ref_type,
                result_ref_id=result.ref_id, result_status=result.status_code,
                completed_at=func.statement_timestamp(),
            )
        )
        if changed.rowcount != 1:
            raise IdempotencyError("SYSTEM_UNAVAILABLE")
