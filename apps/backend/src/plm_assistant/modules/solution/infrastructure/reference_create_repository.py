"""Atomic ReferenceSolution root, initial version and ordered source refs."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.create_reference_solution import ReferenceInitialView
from plm_assistant.modules.solution.application.reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceRequest,
)

from .orm import (
    ReferenceSolutionDocumentRefRow as DocumentRef,
    ReferenceSolutionEvidenceRefRow as EvidenceRef,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceCreateRepository:
    def create(self, transaction: object, *, root_id: uuid.UUID, version_id: uuid.UUID,
               name: str, actor_id: uuid.UUID, sources: ReferenceSourceRequest,
               qualified: QualifiedReferenceSources,
               content_fingerprint: bytes) -> ReferenceInitialView:
        if (type(root_id) is not uuid.UUID or root_id.int == 0
                or type(version_id) is not uuid.UUID or version_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(name) is not str or not name
                or type(sources) is not ReferenceSourceRequest
                or type(qualified) is not QualifiedReferenceSources
                or qualified.scope != sources.scope
                or qualified.project_id != sources.project_id
                or type(content_fingerprint) is not bytes
                or len(content_fingerprint) != 32):
            raise ValueError("validated Reference creation required")
        session = _session(transaction)
        session.execute(insert(Root).values(
            reference_solution_id=root_id, scope=sources.scope,
            project_id=sources.project_id, name=name,
            current_version_ref=version_id, created_by=actor_id,
        ))
        session.execute(insert(Version).values(
            reference_version_id=version_id, reference_solution_id=root_id,
            scope=sources.scope, project_id=sources.project_id, version_no=1,
            applicability=sources.applicability,
            source_project_class=sources.source_project_class,
            deidentification_class=sources.deidentification_class,
            content_fingerprint=content_fingerprint,
            source_fingerprint=qualified.content_fingerprint,
            deidentification_confirmation_id=qualified.deidentification_confirmation_id,
            declared_document_count=len(qualified.document_versions),
            declared_evidence_count=len(qualified.evidence), created_by=actor_id,
        ))
        for ordinal, item in enumerate(qualified.document_versions, 1):
            session.execute(insert(DocumentRef).values(
                reference_version_id=version_id, reference_solution_id=root_id,
                scope=sources.scope, document_version_id=item.document_version_id,
                ordinal=ordinal,
            ))
        for ordinal, item in enumerate(qualified.evidence, 1):
            session.execute(insert(EvidenceRef).values(
                reference_version_id=version_id, reference_solution_id=root_id,
                scope=sources.scope, evidence_id=item.evidence_id, ordinal=ordinal,
            ))
        view = self.view(transaction, root_id=root_id, scope=sources.scope,
                         project_id=sources.project_id)
        if view is None:
            raise RuntimeError("Reference initial view unavailable")
        return view

    def view(self, transaction: object, *, root_id: uuid.UUID, scope: str,
             project_id: uuid.UUID | None) -> ReferenceInitialView | None:
        if (type(root_id) is not uuid.UUID or root_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)):
            return None
        row = _session(transaction).execute(select(
            Root.reference_solution_id, Version.reference_version_id,
            Root.scope, Root.project_id, Root.name,
            Version.source_fingerprint, Version.content_fingerprint,
            Version.deidentification_confirmation_id,
            Root.created_by, Root.created_at,
        ).join(Version, (
            Version.reference_solution_id == Root.reference_solution_id
        )).where(
            Root.reference_solution_id == root_id, Root.scope == scope,
            Root.project_id == project_id, Version.version_no == 1,
            Version.scope == scope, Version.project_id == project_id,
        ).with_for_update(read=True, of=(Root, Version))).one_or_none()
        if row is None:
            return None
        # Replay the immutable first result, never the later eligibility/current pointer.
        return ReferenceInitialView(*row)
