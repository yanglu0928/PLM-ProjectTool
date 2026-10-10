"""PostgreSQL complete-scope locks for Requirement Workflow qualification."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select

from plm_assistant.modules.project.infrastructure.orm import ProjectRow
from plm_assistant.modules.requirement.application.workflow_qualification import (
    RequirementWorkflowApprovedLock,
    RequirementWorkflowDecisionLock,
    RequirementWorkflowScopeLock,
)

from .identity_create_repository import _session
from .orm import (
    RequirementRow,
    RequirementStateDecisionRow,
    RequirementVersionRow,
)
from .version_validation_repository import (
    SqlAlchemyRequirementVersionValidationRepository,
)


class SqlAlchemyRequirementWorkflowQualificationRepository:
    """Build one canonical scope while fencing every Requirement write.

    Requirement write authorization takes an exclusive lock on ProjectRow.
    The shared project lock below therefore prevents new roots/versions and
    state changes from entering between the complete-scope scan and proof.
    """

    def __init__(self) -> None:
        self._snapshots = SqlAlchemyRequirementVersionValidationRepository()

    def lock_complete_scope(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> RequirementWorkflowScopeLock | None:
        if (transaction is None or type(project_id) is not uuid.UUID
                or project_id.int == 0):
            return None
        session = _session(transaction)
        project = session.execute(select(
            ProjectRow.project_id,
        ).where(
            ProjectRow.project_id == project_id,
        ).with_for_update(
            read=True, of=ProjectRow,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if project != project_id:
            return None

        roots = tuple(session.execute(select(
            RequirementRow,
        ).where(
            RequirementRow.project_id == project_id,
        ).order_by(
            RequirementRow.requirement_id,
        ).with_for_update(
            read=True, of=RequirementRow,
        ).execution_options(populate_existing=True)).scalars())
        if not roots:
            return None

        version_rows = tuple(session.execute(select(
            RequirementVersionRow,
        ).where(
            RequirementVersionRow.project_id == project_id,
        ).order_by(
            RequirementVersionRow.requirement_id,
            RequirementVersionRow.version_no,
            RequirementVersionRow.requirement_version_id,
        ).with_for_update(
            read=True, of=RequirementVersionRow,
        ).execution_options(populate_existing=True)).scalars())
        versions: dict[uuid.UUID, list[RequirementVersionRow]] = defaultdict(list)
        for row in version_rows:
            versions[row.requirement_id].append(row)

        decision_rows = tuple(session.execute(select(
            RequirementStateDecisionRow,
        ).where(
            RequirementStateDecisionRow.project_id == project_id,
        ).order_by(
            RequirementStateDecisionRow.requirement_id,
            RequirementStateDecisionRow.after_version.desc(),
            RequirementStateDecisionRow.decision_id,
        ).with_for_update(
            read=True, of=RequirementStateDecisionRow,
        ).execution_options(populate_existing=True)).scalars())
        decisions: dict[uuid.UUID, list[RequirementStateDecisionRow]] = defaultdict(list)
        for row in decision_rows:
            decisions[row.requirement_id].append(row)

        approved: list[RequirementWorkflowApprovedLock] = []
        explained: list[RequirementWorkflowDecisionLock] = []
        for root in roots:
            if root.requirement_state == "ACTIVE":
                locked = self._active(
                    transaction, project_id, root, versions[root.requirement_id],
                )
                if locked is None:
                    return None
                approved.append(locked)
                continue
            locked = self._decision(
                root, decisions[root.requirement_id],
            )
            if locked is None:
                return None
            explained.append(locked)
        if not approved:
            return None
        return RequirementWorkflowScopeLock(
            project_id, len(roots), tuple(approved), tuple(explained),
        )

    def _active(self, transaction, project_id, root, versions):
        if (not versions
                or type(root.current_approved_version_ref) is not uuid.UUID
                or root.current_approved_version_ref.int == 0):
            return None
        latest = versions[-1]
        if (latest.requirement_version_id
                != root.current_approved_version_ref
                or latest.version_state != "APPROVED"
                or type(latest.review_ref) is not uuid.UUID
                or latest.review_ref.int == 0
                or type(latest.review_round_ref) is not uuid.UUID
                or latest.review_round_ref.int == 0):
            return None
        locked_snapshot = self._snapshots.lock_snapshot_and_acceptance_refs(
            transaction, project_id=project_id,
            requirement_id=root.requirement_id,
            requirement_version_id=latest.requirement_version_id,
        )
        if locked_snapshot is None:
            return None
        snapshot, acceptance_refs = locked_snapshot
        return RequirementWorkflowApprovedLock(
            snapshot, latest.requirement_version_id,
            latest.review_ref, latest.review_round_ref, acceptance_refs,
        )

    @staticmethod
    def _decision(root, decisions):
        if root.requirement_state not in {"DEFERRED", "REJECTED", "ARCHIVED"}:
            return None
        if not decisions:
            return None
        latest = decisions[0]
        expected_version = (
            root.lock_version
            if root.requirement_state in {"DEFERRED", "REJECTED"}
            else root.lock_version - 1
        )
        if (latest.after_version != expected_version
                or root.requirement_state == "DEFERRED"
                   and latest.decision_type != "DEFER"
                or root.requirement_state == "REJECTED"
                   and latest.decision_type != "REJECT"
                or root.requirement_state == "ARCHIVED"
                   and latest.decision_type not in {"DEFER", "REJECT"}):
            return None
        return RequirementWorkflowDecisionLock(
            root.requirement_id, root.requirement_state,
            latest.decision_id, root.lock_version,
        )
