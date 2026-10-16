"""PROJECT Reference current-version fixed-reference projection."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.document.infrastructure.orm import DocumentRow, DocumentVersionRow
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceCurrentView, ReferenceDocumentRefView, ReferenceListPage,
    ReferenceSummaryView,
)

from .orm import (
    ReferenceSolutionDocumentRefRow as DocumentRef,
    ReferenceSolutionEvidenceRefRow as EvidenceRef,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceReadRepository:
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     after_reference_solution_id: uuid.UUID | None,
                     limit: int) -> ReferenceListPage:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or (after_reference_solution_id is not None and (
                    type(after_reference_solution_id) is not uuid.UUID
                    or after_reference_solution_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("invalid Reference list query")
        session = _session(transaction)
        statement = select(Root, Version).outerjoin(Version, and_(
            Version.reference_version_id == Root.current_version_ref,
            Version.reference_solution_id == Root.reference_solution_id,
            Version.scope == "PROJECT", Version.project_id == project_id,
        )).where(
            Root.scope == "PROJECT", Root.project_id == project_id,
        )
        if after_reference_solution_id is not None:
            statement = statement.where(
                Root.reference_solution_id > after_reference_solution_id)
        rows = tuple(session.execute(statement.order_by(
            Root.reference_solution_id).limit(limit + 1).with_for_update(
                read=True, of=Root)).all())
        items = []
        for root, version in rows[:limit]:
            if (version is None
                    or root.current_version_ref != version.reference_version_id
                    or version.reference_solution_id != root.reference_solution_id
                    or version.scope != "PROJECT" or version.project_id != project_id
                    or version.deidentification_confirmation_id is not None):
                raise RuntimeError("Reference current version is inconsistent")
            items.append(ReferenceSummaryView(
                reference_solution_id=root.reference_solution_id,
                reference_version_id=version.reference_version_id,
                project_id=project_id, name=root.name,
                eligibility_state=root.eligibility_state,
                version_no=version.version_no, version_state=version.version_state,
                created_at=root.created_at,
                etag=f'"v{root.lock_version}"',
            ))
        has_more = len(rows) > limit
        return ReferenceListPage(
            tuple(items), items[-1].reference_solution_id if has_more else None,
            has_more)

    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    reference_solution_id: uuid.UUID) -> ReferenceCurrentView | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(reference_solution_id) is not uuid.UUID
                or reference_solution_id.int == 0):
            return None
        session = _session(transaction)
        row = session.execute(select(Root, Version).join(
            Version, Version.reference_version_id == Root.current_version_ref,
        ).where(
            Root.reference_solution_id == reference_solution_id,
            Root.scope == "PROJECT", Root.project_id == project_id,
            Version.reference_solution_id == Root.reference_solution_id,
            Version.scope == "PROJECT", Version.project_id == project_id,
        ).with_for_update(read=True, of=(Root, Version))).one_or_none()
        if row is None:
            return None
        root, version = row
        documents = tuple(session.execute(select(
            DocumentRef.ordinal, DocumentRef.document_version_id,
            DocumentRef.scope, DocumentVersionRow.scope,
            DocumentVersionRow.project_id, DocumentVersionRow.document_id,
            DocumentRow.scope, DocumentRow.project_id,
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_version_id == DocumentRef.document_version_id,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).where(
            DocumentRef.reference_version_id == version.reference_version_id,
            DocumentRef.reference_solution_id == reference_solution_id,
        ).order_by(DocumentRef.ordinal)).all())
        evidence = tuple(session.execute(select(
            EvidenceRef.ordinal, EvidenceRef.evidence_id,
            EvidenceRef.scope, EvidenceRow.scope, EvidenceRow.project_id,
        ).join(
            EvidenceRow, EvidenceRow.evidence_id == EvidenceRef.evidence_id,
        ).where(
            EvidenceRef.reference_version_id == version.reference_version_id,
            EvidenceRef.reference_solution_id == reference_solution_id,
        ).order_by(EvidenceRef.ordinal)).all())
        if (len(documents) != version.declared_document_count
                or len(evidence) != version.declared_evidence_count
                or tuple(item.ordinal for item in documents)
                != tuple(range(1, len(documents) + 1))
                or tuple(item.ordinal for item in evidence)
                != tuple(range(1, len(evidence) + 1))
                or any(item[2] != "PROJECT" or item[3] != "PROJECT"
                       or item[4] != project_id or item[6] != "PROJECT"
                       or item[7] != project_id for item in documents)
                or any(item[2] != "PROJECT" or item[3] != "PROJECT"
                       or item[4] != project_id for item in evidence)):
            raise RuntimeError("Reference source projection is inconsistent")
        return ReferenceCurrentView(
            reference_solution_id=root.reference_solution_id,
            reference_version_id=version.reference_version_id,
            project_id=project_id, name=root.name,
            eligibility_state=root.eligibility_state,
            eligibility_reason=root.eligibility_reason,
            version_no=version.version_no, version_state=version.version_state,
            source_project_class=version.source_project_class,
            deidentification_class=version.deidentification_class,
            applicability=dict(version.applicability),
            document_version_ids=tuple(item[1] for item in documents),
            document_refs=tuple(ReferenceDocumentRefView(item[5], item[1])
                                for item in documents),
            evidence_ids=tuple(item[1] for item in evidence),
            source_fingerprint=bytes(version.source_fingerprint),
            content_fingerprint=bytes(version.content_fingerprint),
            created_by=root.created_by, created_at=root.created_at,
            version_created_by=version.created_by,
            version_created_at=version.created_at,
            etag=f'"v{root.lock_version}"',
        )
