"""Current ELIGIBLE Evidence source held in the caller's transaction."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource

from .eligibility_repository import _session
from .orm import EvidenceRow


class SqlAlchemyEvidenceFixedSourceRepository:
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None:
        if (scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise ValueError("validated Evidence scope and identity required")
        row = _session(transaction).execute(
            select(EvidenceRow).where(
                EvidenceRow.evidence_id == evidence_id,
                EvidenceRow.scope == scope,
                EvidenceRow.project_id == project_id,
                EvidenceRow.eligibility_state == "ELIGIBLE",
            ).with_for_update(read=True, of=EvidenceRow)
            .execution_options(populate_existing=True),
        ).scalar_one_or_none()
        if row is None:
            return None
        return LockedEvidenceSource(
            row.evidence_id, row.scope, row.project_id,
            row.document_id, row.document_version_id,
            row.source_parse_record_id, copy.deepcopy(row.locator_payload),
            bytes(row.content_fingerprint), row.lock_version,
        )
