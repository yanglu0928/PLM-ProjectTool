"""PostgreSQL persistence for RequirementPrototypeLink."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.prototype.application.requirement_links import (
    RequirementPrototypeCoverage, RequirementPrototypeLinkError,
    RequirementPrototypeLinkView, StoredRequirementPrototypeLink,
    UncoveredAcceptanceCriterion,
)
from plm_assistant.modules.requirement.infrastructure.orm import (
    RequirementAcceptanceCriterionRow, RequirementRow, RequirementVersionRow,
)

from .identity_create_repository import _session
from .orm import (
    PrototypeRow, PrototypeVersionApprovalTraceManifestRow,
    PrototypeVersionRequirementRefRow, PrototypeVersionRow,
    RequirementPrototypeLinkRow,
)


class SqlAlchemyRequirementPrototypeLinkRepository:
    def prove_current_endpoints(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
    ) -> tuple[uuid.UUID, ...] | None:
        session = _session(transaction)
        prototype = session.execute(select(
            PrototypeVersionRow.prototype_version_id,
        ).join(
            PrototypeRow,
            (PrototypeRow.prototype_id == PrototypeVersionRow.prototype_id)
            & (PrototypeRow.project_id == PrototypeVersionRow.project_id),
        ).join(
            PrototypeVersionApprovalTraceManifestRow,
            PrototypeVersionApprovalTraceManifestRow.prototype_version_id
            == PrototypeVersionRow.prototype_version_id,
        ).join(
            PrototypeVersionRequirementRefRow,
            PrototypeVersionRequirementRefRow.prototype_version_id
            == PrototypeVersionRow.prototype_version_id,
        ).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
            PrototypeVersionRow.prototype_version_id == prototype_version_id,
            PrototypeVersionRow.version_state == "APPROVED",
            PrototypeVersionRow.review_ref.is_not(None),
            PrototypeVersionRow.review_round_ref.is_not(None),
            PrototypeRow.prototype_state == "ACTIVE",
            PrototypeRow.current_approved_version_ref == prototype_version_id,
            PrototypeVersionRequirementRefRow.project_id == project_id,
            PrototypeVersionRequirementRefRow.requirement_id == requirement_id,
            PrototypeVersionRequirementRefRow.requirement_version_id
            == requirement_version_id,
        ).with_for_update(
            read=True, of=(PrototypeRow, PrototypeVersionRow),
        )).scalar_one_or_none()
        if prototype is None:
            return None
        requirement = session.execute(select(
            RequirementVersionRow.requirement_version_id,
        ).join(
            RequirementRow,
            (RequirementRow.requirement_id == RequirementVersionRow.requirement_id)
            & (RequirementRow.project_id == RequirementVersionRow.project_id),
        ).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.requirement_version_id == requirement_version_id,
            RequirementVersionRow.version_state == "APPROVED",
            RequirementVersionRow.review_ref.is_not(None),
            RequirementVersionRow.review_round_ref.is_not(None),
            RequirementRow.requirement_state == "ACTIVE",
            RequirementRow.current_approved_version_ref == requirement_version_id,
        ).with_for_update(
            read=True, of=(RequirementRow, RequirementVersionRow),
        )).scalar_one_or_none()
        if requirement is None:
            return None
        criteria = tuple(session.execute(select(
            RequirementAcceptanceCriterionRow.acceptance_criterion_id,
        ).where(
            RequirementAcceptanceCriterionRow.project_id == project_id,
            RequirementAcceptanceCriterionRow.requirement_id == requirement_id,
            RequirementAcceptanceCriterionRow.requirement_version_id
            == requirement_version_id,
        ).order_by(
            RequirementAcceptanceCriterionRow.acceptance_criterion_id,
        ).with_for_update(read=True)).scalars())
        return criteria or None

    def create_active(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
        purpose: str, coverage: RequirementPrototypeCoverage,
        actor_id: uuid.UUID,
    ) -> StoredRequirementPrototypeLink:
        session = _session(transaction)
        identity = {
            "project_id": project_id, "requirement_id": requirement_id,
            "requirement_version_id": requirement_version_id,
            "prototype_id": prototype_id,
            "prototype_version_id": prototype_version_id,
            "purpose": purpose,
            "coverage": self._coverage_payload(coverage),
        }
        inserted = session.execute(pg_insert(
            RequirementPrototypeLinkRow,
        ).values(**identity, coverage_schema_version=1, created_by=actor_id)
        .on_conflict_do_nothing(
            index_elements=["project_id", "requirement_id", "prototype_id", "purpose"],
            index_where=RequirementPrototypeLinkRow.link_state == "ACTIVE",
        ).returning(
            RequirementPrototypeLinkRow.requirement_prototype_link_id,
        )).scalar_one_or_none()
        if inserted is not None:
            return StoredRequirementPrototypeLink(inserted, True)
        existing = session.execute(select(
            RequirementPrototypeLinkRow.requirement_prototype_link_id,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_id == requirement_id,
            RequirementPrototypeLinkRow.prototype_id == prototype_id,
            RequirementPrototypeLinkRow.purpose == purpose,
            RequirementPrototypeLinkRow.link_state == "ACTIVE",
        )).scalar_one_or_none()
        if existing is None:
            raise RequirementPrototypeLinkError()
        return StoredRequirementPrototypeLink(existing, False)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            link_id: uuid.UUID) -> RequirementPrototypeLinkView | None:
        row = _session(transaction).execute(select(
            RequirementPrototypeLinkRow,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_prototype_link_id == link_id,
        )).scalar_one_or_none()
        return None if row is None else self._view(row)

    def list_links(self, transaction: object, *, project_id: uuid.UUID,
                   after_link_id: uuid.UUID | None,
                   limit: int) -> tuple[RequirementPrototypeLinkView, ...]:
        query = select(RequirementPrototypeLinkRow).where(
            RequirementPrototypeLinkRow.project_id == project_id,
        )
        if after_link_id is not None:
            query = query.where(
                RequirementPrototypeLinkRow.requirement_prototype_link_id
                < after_link_id,
            )
        rows = _session(transaction).execute(query.order_by(
            RequirementPrototypeLinkRow.requirement_prototype_link_id.desc(),
        ).limit(limit)).scalars()
        return tuple(self._view(row) for row in rows)

    def lock_active(self, transaction: object, *, project_id: uuid.UUID,
                    link_id: uuid.UUID) -> RequirementPrototypeLinkView | None:
        row = _session(transaction).execute(select(
            RequirementPrototypeLinkRow,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_prototype_link_id == link_id,
            RequirementPrototypeLinkRow.link_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        return None if row is None else self._view(row)

    def revoke_active(self, transaction: object, *, project_id: uuid.UUID,
                      link_id: uuid.UUID) -> None:
        changed = _session(transaction).execute(update(
            RequirementPrototypeLinkRow,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_prototype_link_id == link_id,
            RequirementPrototypeLinkRow.link_state == "ACTIVE",
            RequirementPrototypeLinkRow.lock_version == 0,
        ).values(link_state="REVOKED", lock_version=1))
        if changed.rowcount != 1:
            raise RequirementPrototypeLinkError("RESOURCE_NOT_FOUND")

    def supersede_active(self, transaction: object, *, project_id: uuid.UUID,
                         link_id: uuid.UUID,
                         replacement_id: uuid.UUID) -> None:
        changed = _session(transaction).execute(update(
            RequirementPrototypeLinkRow,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_prototype_link_id == link_id,
            RequirementPrototypeLinkRow.link_state == "ACTIVE",
            RequirementPrototypeLinkRow.lock_version == 0,
        ).values(
            link_state="SUPERSEDED", lock_version=1,
            superseded_by_ref=replacement_id,
        ))
        if changed.rowcount != 1:
            raise RequirementPrototypeLinkError("RESOURCE_NOT_FOUND")

    def create_replacement(
        self, transaction: object, *, link_id: uuid.UUID,
        project_id: uuid.UUID, requirement_id: uuid.UUID,
        requirement_version_id: uuid.UUID, prototype_id: uuid.UUID,
        prototype_version_id: uuid.UUID, purpose: str,
        coverage: RequirementPrototypeCoverage, actor_id: uuid.UUID,
    ) -> None:
        inserted = _session(transaction).execute(pg_insert(
            RequirementPrototypeLinkRow,
        ).values(
            requirement_prototype_link_id=link_id, project_id=project_id,
            requirement_id=requirement_id,
            requirement_version_id=requirement_version_id,
            prototype_id=prototype_id,
            prototype_version_id=prototype_version_id, purpose=purpose,
            coverage_schema_version=1,
            coverage=self._coverage_payload(coverage), created_by=actor_id,
        ).returning(
            RequirementPrototypeLinkRow.requirement_prototype_link_id,
        )).scalar_one_or_none()
        if inserted != link_id:
            raise RequirementPrototypeLinkError()

    def replacement_matches(self, transaction: object, *, project_id: uuid.UUID,
                            link_id: uuid.UUID,
                            replacement_id: uuid.UUID) -> bool:
        found = _session(transaction).execute(select(
            RequirementPrototypeLinkRow.requirement_prototype_link_id,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.requirement_prototype_link_id == link_id,
            RequirementPrototypeLinkRow.link_state == "SUPERSEDED",
            RequirementPrototypeLinkRow.lock_version == 1,
            RequirementPrototypeLinkRow.superseded_by_ref == replacement_id,
        )).scalar_one_or_none()
        return found == link_id

    @classmethod
    def _view(cls, row):
        raw = dict(row.coverage)
        try:
            coverage = RequirementPrototypeCoverage(
                tuple(uuid.UUID(value) for value in
                      raw["covered_acceptance_criterion_refs"]),
                tuple(UncoveredAcceptanceCriterion(
                    uuid.UUID(value["acceptance_criterion_ref"]), value["reason"],
                ) for value in raw["uncovered_acceptance_criteria"]),
            )
        except (KeyError, TypeError, ValueError):
            raise RequirementPrototypeLinkError() from None
        return RequirementPrototypeLinkView(
            row.requirement_prototype_link_id, row.project_id,
            row.requirement_id, row.requirement_version_id,
            row.prototype_id, row.prototype_version_id, row.purpose,
            coverage, row.link_state, row.lock_version, row.created_by,
            row.created_at, row.superseded_by_ref,
        )

    @staticmethod
    def _coverage_payload(value):
        return {
            "covered_acceptance_criterion_refs": [
                str(item) for item in value.covered_acceptance_criterion_refs
            ],
            "uncovered_acceptance_criteria": [{
                "acceptance_criterion_ref": str(item.acceptance_criterion_ref),
                "reason": item.reason,
            } for item in value.uncovered_acceptance_criteria],
        }
