"""Locked current PrototypeVersion and active Link facts for Workflow Owner."""

from __future__ import annotations

import hmac
import uuid

from sqlalchemy import select

from plm_assistant.modules.prototype.application.requirement_links import (
    RequirementPrototypeLinkError,
    RequirementPrototypeLinkService,
)
from plm_assistant.modules.prototype.application.workflow_scope_lock import (
    PrototypeRootLock,
)
from plm_assistant.modules.prototype.application.workflow_version_links import (
    PrototypeWorkflowVersionLinksLock,
    PrototypeWorkflowVersionLock,
)

from .approval_trace_repository import SqlAlchemyPrototypeApprovalTraceRepository
from .orm import (
    PrototypeVersionApprovalTraceManifestRow,
    PrototypeVersionReviewStateResultRow,
    PrototypeVersionRow,
    RequirementPrototypeLinkRow,
)
from .requirement_link_repository import SqlAlchemyRequirementPrototypeLinkRepository
from .scope_decision_repository import _session
from .version_read_repository import SqlAlchemyPrototypeVersionReadRepository


class SqlAlchemyPrototypeWorkflowVersionLinksRepository:
    """Consume P01's project fence in the same transaction; never authorize PASS."""

    def __init__(self) -> None:
        self._versions = SqlAlchemyPrototypeVersionReadRepository()
        self._traces = SqlAlchemyPrototypeApprovalTraceRepository()

    def lock_current_versions_and_links(
        self, transaction: object, *, project_id: uuid.UUID,
        roots: tuple[PrototypeRootLock, ...],
    ) -> PrototypeWorkflowVersionLinksLock | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(roots) is not tuple
                or any(type(root) is not PrototypeRootLock
                       or root.project_id != project_id for root in roots)
                or len({root.prototype_id for root in roots}) != len(roots)):
            return None
        session = _session(transaction)
        output: list[PrototypeWorkflowVersionLock] = []
        current: dict[uuid.UUID, uuid.UUID] = {}
        for root in roots:
            if root.state == "NOT_REQUIRED":
                if root.decision is None or root.current_approved_version_ref is not None:
                    return None
                continue
            if (root.state != "ACTIVE" or root.decision is not None
                    or type(root.current_approved_version_ref) is not uuid.UUID
                    or root.current_approved_version_ref.int == 0):
                return None
            version_id = root.current_approved_version_ref
            row = session.execute(select(PrototypeVersionRow).where(
                PrototypeVersionRow.project_id == project_id,
                PrototypeVersionRow.prototype_id == root.prototype_id,
                PrototypeVersionRow.prototype_version_id == version_id,
            ).with_for_update(
                read=True, of=PrototypeVersionRow,
            ).execution_options(populate_existing=True)).scalar_one_or_none()
            if (row is None or row.version_state != "APPROVED"
                    or row.review_ref is None or row.review_round_ref is None):
                return None
            approval = session.execute(select(
                PrototypeVersionReviewStateResultRow,
            ).where(
                PrototypeVersionReviewStateResultRow.project_id == project_id,
                PrototypeVersionReviewStateResultRow.prototype_id
                == root.prototype_id,
                PrototypeVersionReviewStateResultRow.prototype_version_id
                == version_id,
                PrototypeVersionReviewStateResultRow.event_type == "APPROVED",
            ).with_for_update(
                read=True, of=PrototypeVersionReviewStateResultRow,
            ).execution_options(populate_existing=True)).scalar_one_or_none()
            if (approval is None
                    or approval.current_approved_version_ref != version_id
                    or approval.review_id != row.review_ref
                    or approval.review_round_id != row.review_round_ref
                    or approval.lock_version > root.lock_version):
                return None
            manifest = session.execute(select(
                PrototypeVersionApprovalTraceManifestRow,
            ).where(
                PrototypeVersionApprovalTraceManifestRow.project_id == project_id,
                PrototypeVersionApprovalTraceManifestRow.prototype_id
                == root.prototype_id,
                PrototypeVersionApprovalTraceManifestRow.prototype_version_id
                == version_id,
            ).with_for_update(
                read=True, of=PrototypeVersionApprovalTraceManifestRow,
            ).execution_options(populate_existing=True)).scalar_one_or_none()
            if (manifest is None
                    or manifest.review_state_result_id != approval.review_state_result_id
                    or manifest.review_id != row.review_ref
                    or manifest.review_round_id != row.review_round_ref
                    or manifest.approved_by != approval.actor_id
                    or not hmac.compare_digest(
                        bytes(manifest.content_fingerprint),
                        bytes(row.content_fingerprint))):
                return None
            try:
                snapshot = self._versions.get(
                    transaction, project_id=project_id,
                    prototype_id=root.prototype_id, version_id=version_id,
                )
            except (RuntimeError, ValueError, TypeError):
                return None
            if (snapshot is None or snapshot.version_state != "APPROVED"
                    or snapshot.content_fingerprint
                    != bytes(row.content_fingerprint).hex()
                    or manifest.declared_artifact_count != len(snapshot.artifact_refs)
                    or manifest.declared_requirement_count
                    != len(snapshot.requirement_refs)
                    or manifest.template_id != snapshot.template_id
                    or manifest.template_version_id != snapshot.template_version_id
                    or self._traces.manifest_matches(
                        transaction, prototype_version_id=version_id,
                        prototype_id=root.prototype_id, project_id=project_id,
                        review_state_result_id=approval.review_state_result_id,
                        review_id=row.review_ref,
                        review_round_id=row.review_round_ref,
                        approved_by=approval.actor_id,
                    ) is not True):
                return None
            current[root.prototype_id] = version_id
            output.append(PrototypeWorkflowVersionLock(
                snapshot, row.review_ref, row.review_round_ref,
                approval.review_state_result_id, approval.actor_id,
            ))

        link_rows = tuple(session.execute(select(
            RequirementPrototypeLinkRow,
        ).where(
            RequirementPrototypeLinkRow.project_id == project_id,
            RequirementPrototypeLinkRow.link_state == "ACTIVE",
        ).order_by(
            RequirementPrototypeLinkRow.requirement_prototype_link_id,
        ).with_for_update(
            read=True, of=RequirementPrototypeLinkRow,
        ).execution_options(populate_existing=True)).scalars())
        links = []
        for row in link_rows:
            if (row.lock_version != 0 or row.superseded_by_ref is not None
                    or current.get(row.prototype_id) != row.prototype_version_id):
                return None
            try:
                view = SqlAlchemyRequirementPrototypeLinkRepository._view(row)
                canonical = RequirementPrototypeLinkService._coverage(view.coverage)
                payload = SqlAlchemyRequirementPrototypeLinkRepository._coverage_payload(
                    canonical)
            except (RequirementPrototypeLinkError, TypeError, ValueError):
                return None
            if payload != row.coverage:
                return None
            links.append(view)
        return PrototypeWorkflowVersionLinksLock(tuple(output), tuple(links))
