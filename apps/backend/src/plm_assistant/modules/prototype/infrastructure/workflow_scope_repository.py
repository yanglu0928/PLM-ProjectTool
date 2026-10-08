"""PostgreSQL complete Prototype root/decision scan for Workflow Owner."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select

from plm_assistant.modules.project.infrastructure.orm import ProjectRow
from plm_assistant.modules.prototype.application.workflow_scope_lock import (
    PrototypeRootLock,
    prove_not_required_decision,
)

from .orm import (
    PrototypeRow,
    PrototypeScopeDecisionRequirementRefRow,
    PrototypeScopeDecisionResultRow,
    PrototypeScopeDecisionRow,
)
from .scope_decision_repository import _session


class SqlAlchemyPrototypeWorkflowScopeRepository:
    """Lock the project fence and all Prototype roots/decision witnesses.

    Prototype writes first take an exclusive ProjectRow lock via project
    authorization. The shared lock therefore prevents inserts and state edits
    while the caller proves the complete Requirement/Prototype graph.
    """

    def lock_current_roots(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> tuple[PrototypeRootLock, ...] | None:
        if type(project_id) is not uuid.UUID or project_id.int == 0:
            return None
        session = _session(transaction)
        project = session.execute(select(ProjectRow.project_id).where(
            ProjectRow.project_id == project_id,
        ).with_for_update(
            read=True, of=ProjectRow,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if project != project_id:
            return None

        def locked(model, *order):
            return tuple(session.execute(select(model).where(
                model.project_id == project_id,
            ).order_by(*order).with_for_update(
                read=True, of=model,
            ).execution_options(populate_existing=True)).scalars())

        roots = locked(PrototypeRow, PrototypeRow.prototype_id)
        decisions = locked(PrototypeScopeDecisionRow,
                           PrototypeScopeDecisionRow.prototype_id)
        refs = locked(PrototypeScopeDecisionRequirementRefRow,
                      PrototypeScopeDecisionRequirementRefRow.scope_decision_id,
                      PrototypeScopeDecisionRequirementRefRow.ordinal)
        results = locked(PrototypeScopeDecisionResultRow,
                         PrototypeScopeDecisionResultRow.prototype_id)
        by_decision: dict[uuid.UUID, list] = defaultdict(list)
        by_ref: dict[uuid.UUID, list] = defaultdict(list)
        by_result: dict[uuid.UUID, list] = defaultdict(list)
        for row in decisions:
            by_decision[row.prototype_id].append(row)
        for row in refs:
            by_ref[row.scope_decision_id].append(row)
        for row in results:
            by_result[row.prototype_id].append(row)
        if (len(decisions) != len(results)
                or {row.prototype_id for row in decisions}
                   != {row.prototype_id for row in results}
                or {row.scope_decision_id for row in decisions}
                   != set(by_ref)):
            return None
        output: list[PrototypeRootLock] = []
        for root in roots:
            if root.prototype_state not in {"ACTIVE", "NOT_REQUIRED"}:
                return None  # no frozen policy for ARCHIVED/RESTRICTED scope yet
            selected = by_decision[root.prototype_id]
            matching_results = by_result[root.prototype_id]
            if root.prototype_state == "ACTIVE":
                if selected or matching_results:
                    return None
                proof = None
            else:
                if len(selected) != 1 or len(matching_results) != 1:
                    return None
                proof = prove_not_required_decision(
                    root, selected[0],
                    tuple(by_ref[selected[0].scope_decision_id]),
                    matching_results[0],
                )
                if proof is None:
                    return None
            output.append(PrototypeRootLock(
                project_id, root.prototype_id, root.prototype_state,
                root.current_approved_version_ref, root.lock_version, proof,
            ))
        if {row.prototype_id for row in decisions} - {
            row.prototype_id for row in roots
        }:
            return None
        return tuple(output)
