"""PostgreSQL persistence and DAG proof for RequirementRelation."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.requirement.application.relations import (
    RequirementRelationError, RequirementRelationView, RequirementVersionRef,
    StoredRequirementRelation,
)

from .identity_create_repository import _session
from .orm import RequirementRelationRow, RequirementVersionRow


_REACHABLE = text("""
WITH RECURSIVE walk(version_id) AS (
  SELECT CAST(:target AS uuid)
  UNION
  SELECT edge.target_requirement_version_id
    FROM walk JOIN plm.req_relations edge
      ON edge.source_requirement_version_id=walk.version_id
   WHERE edge.project_id=CAST(:project AS uuid)
     AND edge.relation_state='ACTIVE'
     AND edge.relation_type=:relation_type
     AND (CAST(:exclude AS uuid) IS NULL
          OR edge.requirement_relation_id<>CAST(:exclude AS uuid))
)
SELECT EXISTS(SELECT 1 FROM walk WHERE version_id=CAST(:source AS uuid))
""")


class SqlAlchemyRequirementRelationRepository:
    def endpoints_exist(self, transaction: object, *, project_id: uuid.UUID,
                        source: RequirementVersionRef,
                        target: RequirementVersionRef) -> bool:
        rows = _session(transaction).execute(select(
            RequirementVersionRow.requirement_id,
            RequirementVersionRow.requirement_version_id,
        ).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_version_id.in_((
                source.requirement_version_id,
                target.requirement_version_id,
            )),
        ).with_for_update(read=True)).all()
        return set(rows) == {
            (source.requirement_id, source.requirement_version_id),
            (target.requirement_id, target.requirement_version_id),
        }

    def assert_acyclic(self, transaction: object, *, project_id: uuid.UUID,
                       source_version_id: uuid.UUID, target_version_id: uuid.UUID,
                       relation_type: str,
                       exclude_relation_id: uuid.UUID | None = None) -> None:
        if relation_type not in ("DEPENDS_ON", "PARENT_OF"):
            return
        reachable = _session(transaction).execute(_REACHABLE, {
            "project": project_id, "source": source_version_id,
            "target": target_version_id, "relation_type": relation_type,
            "exclude": exclude_relation_id,
        }).scalar_one()
        if reachable is True:
            raise RequirementRelationError("REQUIREMENT_RELATION_CYCLE")

    def create_active(self, transaction: object, *, project_id: uuid.UUID,
                      source: RequirementVersionRef, target: RequirementVersionRef,
                      relation_type: str,
                      actor_id: uuid.UUID) -> StoredRequirementRelation:
        session = _session(transaction)
        identity = {
            "project_id": project_id,
            "source_requirement_id": source.requirement_id,
            "source_requirement_version_id": source.requirement_version_id,
            "target_requirement_id": target.requirement_id,
            "target_requirement_version_id": target.requirement_version_id,
            "relation_type": relation_type,
        }
        inserted = session.execute(pg_insert(RequirementRelationRow).values(
            **identity, created_by=actor_id,
        ).on_conflict_do_nothing(
            index_elements=[
                "project_id", "source_requirement_version_id",
                "relation_type", "target_requirement_version_id",
            ], index_where=RequirementRelationRow.relation_state == "ACTIVE",
        ).returning(RequirementRelationRow.requirement_relation_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return StoredRequirementRelation(inserted, True)
        existing = session.execute(select(
            RequirementRelationRow.requirement_relation_id,
        ).where(
            RequirementRelationRow.relation_state == "ACTIVE",
            *(getattr(RequirementRelationRow, name) == value
              for name, value in identity.items()),
        )).scalar_one_or_none()
        if existing is None:
            raise RequirementRelationError()
        return StoredRequirementRelation(existing, False)

    def exists(self, transaction: object, *, project_id: uuid.UUID,
               relation_id: uuid.UUID) -> bool:
        return _session(transaction).execute(select(
            RequirementRelationRow.requirement_relation_id,
        ).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
        )).scalar_one_or_none() == relation_id

    def get(self, transaction: object, *, project_id: uuid.UUID,
            relation_id: uuid.UUID) -> RequirementRelationView | None:
        row = _session(transaction).execute(select(RequirementRelationRow).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
        )).scalar_one_or_none()
        return None if row is None else self._view(row)

    def list_relations(self, transaction: object, *, project_id: uuid.UUID,
                       after_relation_id: uuid.UUID | None,
                       limit: int) -> tuple[RequirementRelationView, ...]:
        query = select(RequirementRelationRow).where(
            RequirementRelationRow.project_id == project_id)
        if after_relation_id is not None:
            query = query.where(
                RequirementRelationRow.requirement_relation_id < after_relation_id)
        rows = _session(transaction).execute(query.order_by(
            RequirementRelationRow.requirement_relation_id.desc()
        ).limit(limit)).scalars().all()
        return tuple(self._view(row) for row in rows)

    def lock_active(self, transaction: object, *, project_id: uuid.UUID,
                    relation_id: uuid.UUID) -> RequirementRelationView | None:
        row = _session(transaction).execute(select(RequirementRelationRow).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
            RequirementRelationRow.relation_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True)).scalar_one_or_none()
        return None if row is None else self._view(row)

    def revoke_active(self, transaction: object, *, project_id: uuid.UUID,
                      relation_id: uuid.UUID) -> None:
        changed = _session(transaction).execute(update(
            RequirementRelationRow).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
            RequirementRelationRow.relation_state == "ACTIVE",
            RequirementRelationRow.lock_version == 0,
        ).values(relation_state="REVOKED", lock_version=1))
        if changed.rowcount != 1:
            raise RequirementRelationError("RESOURCE_NOT_FOUND")

    def supersede_active(self, transaction: object, *, project_id: uuid.UUID,
                         relation_id: uuid.UUID,
                         replacement_id: uuid.UUID) -> None:
        changed = _session(transaction).execute(update(
            RequirementRelationRow).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
            RequirementRelationRow.relation_state == "ACTIVE",
            RequirementRelationRow.lock_version == 0,
        ).values(relation_state="SUPERSEDED", lock_version=1,
                 superseded_by_ref=replacement_id))
        if changed.rowcount != 1:
            raise RequirementRelationError("RESOURCE_NOT_FOUND")

    def replacement_matches(self, transaction: object, *, project_id: uuid.UUID,
                            relation_id: uuid.UUID,
                            replacement_id: uuid.UUID) -> bool:
        found = _session(transaction).execute(select(
            RequirementRelationRow.requirement_relation_id,
        ).where(
            RequirementRelationRow.project_id == project_id,
            RequirementRelationRow.requirement_relation_id == relation_id,
            RequirementRelationRow.relation_state == "SUPERSEDED",
            RequirementRelationRow.lock_version == 1,
            RequirementRelationRow.superseded_by_ref == replacement_id,
        )).scalar_one_or_none()
        return found == relation_id

    @staticmethod
    def _view(row):
        return RequirementRelationView(
            row.requirement_relation_id, row.project_id,
            RequirementVersionRef(
                row.source_requirement_id,
                row.source_requirement_version_id),
            RequirementVersionRef(
                row.target_requirement_id,
                row.target_requirement_version_id),
            row.relation_type, row.relation_state, row.lock_version,
            row.created_by, row.created_at, row.superseded_by_ref,
        )
