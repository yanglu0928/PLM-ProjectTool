"""Transactional PostgreSQL reservation and immutable replay lookup."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.idempotency_orm import IdempotencyReceiptRow


class SqlAlchemyIdempotencyReceipts:
    """Reserve and complete inside the caller's business/Audit transaction."""

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
