"""PostgreSQL persistence for Prototype approval Trace manifests."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.prototype.application.approval_trace import (
    PrototypeApprovalTraceError,
    PrototypeApprovalTraceManifest,
)
from plm_assistant.modules.trace.infrastructure.orm import TraceLinkRow

from .orm import (
    PrototypeVersionApprovalTraceManifestRow,
    PrototypeVersionApprovalTraceSourceRow,
)


class SqlAlchemyPrototypeApprovalTraceRepository:
    def insert_manifest(
        self, transaction: object, *, manifest: PrototypeApprovalTraceManifest,
    ) -> None:
        if type(manifest) is not PrototypeApprovalTraceManifest:
            raise PrototypeApprovalTraceError()
        manifest.__post_init__()
        session = _session(transaction)
        manifest_id = uuid.UUID(new_uuid7())
        session.add(PrototypeVersionApprovalTraceManifestRow(
            approval_trace_manifest_id=manifest_id,
            prototype_version_id=manifest.prototype_version_id,
            prototype_id=manifest.prototype_id,
            project_id=manifest.project_id,
            review_state_result_id=manifest.review_state_result_id,
            review_id=manifest.review_id,
            review_round_id=manifest.review_round_id,
            template_id=manifest.template_id,
            template_version_id=manifest.template_version_id,
            content_fingerprint=manifest.content_fingerprint,
            declared_artifact_count=manifest.declared_artifact_count,
            declared_requirement_count=manifest.declared_requirement_count,
            declared_trace_link_count=len(manifest.sources),
            approved_by=manifest.approved_by,
        ))
        try:
            session.flush()
            for item in manifest.sources:
                session.add(PrototypeVersionApprovalTraceSourceRow(
                    approval_trace_source_id=uuid.UUID(new_uuid7()),
                    approval_trace_manifest_id=manifest_id,
                    prototype_version_id=manifest.prototype_version_id,
                    prototype_id=manifest.prototype_id,
                    project_id=manifest.project_id,
                    ordinal=item.ordinal,
                    source_kind=item.source_kind,
                    source_owner_module=item.source.owner_module,
                    source_object_type=item.source.object_type,
                    source_object_id=item.source.object_id,
                    source_version_id=item.source.version_id,
                    source_project_id=item.source.project_id,
                    relation_type=item.relation_type,
                    trace_link_id=item.trace_link_id,
                ))
            session.flush()
        except Exception:
            raise PrototypeApprovalTraceError() from None

    def manifest_matches(
        self, transaction: object, *, prototype_version_id: uuid.UUID,
        prototype_id: uuid.UUID, project_id: uuid.UUID,
        review_state_result_id: uuid.UUID, review_id: uuid.UUID,
        review_round_id: uuid.UUID, approved_by: uuid.UUID,
    ) -> bool:
        if not _ids(
                prototype_version_id, prototype_id, project_id,
                review_state_result_id, review_id, review_round_id,
                approved_by):
            return False
        session = _session(transaction)
        manifest = session.execute(select(
            PrototypeVersionApprovalTraceManifestRow,
        ).where(
            PrototypeVersionApprovalTraceManifestRow.prototype_version_id
            == prototype_version_id,
            PrototypeVersionApprovalTraceManifestRow.prototype_id
            == prototype_id,
            PrototypeVersionApprovalTraceManifestRow.project_id == project_id,
            PrototypeVersionApprovalTraceManifestRow.review_state_result_id
            == review_state_result_id,
            PrototypeVersionApprovalTraceManifestRow.review_id == review_id,
            PrototypeVersionApprovalTraceManifestRow.review_round_id
            == review_round_id,
            PrototypeVersionApprovalTraceManifestRow.approved_by == approved_by,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if manifest is None:
            return False
        active_count = session.execute(select(func.count()).select_from(
            PrototypeVersionApprovalTraceSourceRow,
        ).join(
            TraceLinkRow,
            TraceLinkRow.trace_link_id
            == PrototypeVersionApprovalTraceSourceRow.trace_link_id,
        ).where(
            PrototypeVersionApprovalTraceSourceRow.approval_trace_manifest_id
            == manifest.approval_trace_manifest_id,
            TraceLinkRow.link_state == "ACTIVE",
        )).scalar_one()
        return active_count == manifest.declared_trace_link_count


def _session(transaction: object) -> Session:
    session = getattr(transaction, "session", None)
    if not isinstance(session, Session) or not session.in_transaction():
        raise PrototypeApprovalTraceError()
    return session


def _ids(*values: object) -> bool:
    return all(type(value) is uuid.UUID and value.int != 0
               for value in values)
