"""Reference revision storage: root lock, immutable version and first result."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update

from plm_assistant.modules.solution.application.reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceRequest,
)
from plm_assistant.modules.solution.application.revise_reference_solution import (
    CurrentReference, ReferenceRevisionView,
)

from .orm import (
    ReferenceSolutionDocumentRefRow as DocumentRef,
    ReferenceSolutionEvidenceRefRow as EvidenceRef,
    ReferenceSolutionReviseResultRow as Result,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceReviseRepository:
    def current(self, transaction: object, *, root_id: uuid.UUID, scope: str,
                project_id: uuid.UUID | None) -> CurrentReference | None:
        if (type(root_id) is not uuid.UUID or root_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)):
            return None
        session = _session(transaction)
        root = session.execute(select(Root).where(
            Root.reference_solution_id == root_id, Root.scope == scope,
            Root.project_id == project_id,
        ).with_for_update(of=Root)).scalar_one_or_none()
        if root is None or root.current_version_ref is None:
            return None
        version = session.execute(select(Version).where(
            Version.reference_version_id == root.current_version_ref,
            Version.reference_solution_id == root_id, Version.scope == scope,
            Version.project_id == project_id,
        )).scalar_one_or_none()
        if version is None:
            raise RuntimeError("Reference current version is invalid")
        return CurrentReference(
            root_id, version.reference_version_id, scope, project_id,
            root.name, version.version_no, root.lock_version, root.eligibility_state)

    def revise(self, transaction: object, *, current: CurrentReference,
               version_id: uuid.UUID, actor_id: uuid.UUID,
               sources: ReferenceSourceRequest, qualified: QualifiedReferenceSources,
               content_fingerprint: bytes) -> ReferenceRevisionView:
        if (type(current) is not CurrentReference
                or type(version_id) is not uuid.UUID or version_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(sources) is not ReferenceSourceRequest
                or type(qualified) is not QualifiedReferenceSources
                or current.scope != sources.scope or current.project_id != sources.project_id
                or qualified.scope != sources.scope or qualified.project_id != sources.project_id
                or type(content_fingerprint) is not bytes or len(content_fingerprint) != 32):
            raise ValueError("validated Reference revision required")
        session = _session(transaction)
        version = session.execute(insert(Version).values(
            reference_version_id=version_id,
            reference_solution_id=current.reference_solution_id,
            scope=current.scope, project_id=current.project_id,
            version_no=current.version_no+1, applicability=sources.applicability,
            source_project_class=sources.source_project_class,
            deidentification_class=sources.deidentification_class,
            content_fingerprint=content_fingerprint,
            source_fingerprint=qualified.content_fingerprint,
            deidentification_confirmation_id=qualified.deidentification_confirmation_id,
            declared_document_count=len(qualified.document_versions),
            declared_evidence_count=len(qualified.evidence),
            supersedes_version_ref=current.reference_version_id,
            created_by=actor_id,
        ).returning(Version.created_at)).one()
        for ordinal, item in enumerate(qualified.document_versions, 1):
            session.execute(insert(DocumentRef).values(
                reference_version_id=version_id,
                reference_solution_id=current.reference_solution_id,
                scope=current.scope, document_version_id=item.document_version_id,
                ordinal=ordinal,
            ))
        for ordinal, item in enumerate(qualified.evidence, 1):
            session.execute(insert(EvidenceRef).values(
                reference_version_id=version_id,
                reference_solution_id=current.reference_solution_id,
                scope=current.scope, evidence_id=item.evidence_id, ordinal=ordinal,
            ))
        changed = session.execute(update(Root).where(
            Root.reference_solution_id == current.reference_solution_id,
            Root.scope == current.scope,
            Root.project_id == current.project_id,
            Root.current_version_ref == current.reference_version_id,
            Root.lock_version == current.lock_version,
        ).values(current_version_ref=version_id,
                 lock_version=current.lock_version+1)).rowcount
        if changed != 1:
            raise RuntimeError("Reference revision concurrency conflict")
        session.execute(insert(Result).values(
            reference_version_id=version_id,
            reference_solution_id=current.reference_solution_id,
            scope=current.scope, version_no=current.version_no+1,
            supersedes_version_ref=current.reference_version_id,
            content_fingerprint=content_fingerprint,
            source_fingerprint=qualified.content_fingerprint,
            created_at=version.created_at,
            result_lock_version=current.lock_version+1,
        ))
        return ReferenceRevisionView(
            current.reference_solution_id, version_id, current.scope,
            current.project_id, current.version_no+1,
            current.reference_version_id, content_fingerprint,
            qualified.content_fingerprint, version.created_at,
            current.lock_version+1)

    def result(self, transaction: object, *, version_id: uuid.UUID, scope: str,
               project_id: uuid.UUID | None) -> ReferenceRevisionView | None:
        if type(version_id) is not uuid.UUID or version_id.int == 0:
            return None
        row = _session(transaction).execute(select(
            Result.reference_solution_id, Result.reference_version_id,
            Result.scope, Root.project_id, Result.version_no,
            Result.supersedes_version_ref, Result.content_fingerprint,
            Result.source_fingerprint, Result.created_at,
            Result.result_lock_version,
        ).join(Root, Root.reference_solution_id == Result.reference_solution_id).where(
            Result.reference_version_id == version_id, Result.scope == scope,
            Root.scope == scope, Root.project_id == project_id,
        )).one_or_none()
        return ReferenceRevisionView(*row) if row is not None else None
