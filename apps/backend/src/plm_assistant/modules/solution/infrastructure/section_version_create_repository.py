"""Persist a SectionVersion and immutable first result in one caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.create_section_version import (
    SectionVersionInitialView,
)
from plm_assistant.modules.solution.application.prove_section_version_input import (
    ProvenSectionVersionInput,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
)

from .orm import (
    SolutionSectionEvidenceRefRow,
    SolutionSectionRequirementRefRow,
    SolutionSectionVersionCreateResultRow,
    SolutionSectionVersionRow,
)
from .reference_deidentification_repository import _session


class SqlAlchemySectionVersionCreateRepository:
    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenSectionVersionInput) -> SectionVersionInitialView:
        session = _session(transaction)
        draft = proof.draft
        assumptions = draft.assumptions()
        exclusions = draft.exclusions()
        counts = dict(
            declared_requirement_count=len(draft.requirement_refs),
            declared_evidence_count=len(draft.evidence_ids),
        )
        created_at = session.execute(insert(SolutionSectionVersionRow).values(
            solution_section_version_id=version_id,
            solution_section_id=draft.solution_section_id,
            project_id=draft.project_id,
            version_no=proof.base.next_version_no,
            version_state="DRAFT",
            title=draft.title,
            content_document_version_ref=draft.content_document_version_ref,
            content_artifact_ref=None,
            content_fingerprint=proof.content_fingerprint,
            assumptions=assumptions, exclusions=exclusions,
            supersedes_version_ref=proof.base.supersedes_version_id,
            review_ref=None, review_round_ref=None,
            created_by=actor_id,
            **counts,
        ).returning(SolutionSectionVersionRow.created_at)).scalar_one()
        for ordinal, item in enumerate(draft.requirement_refs, 1):
            session.execute(insert(SolutionSectionRequirementRefRow).values(
                solution_section_version_id=version_id,
                solution_section_id=draft.solution_section_id,
                project_id=draft.project_id,
                requirement_id=item.requirement_id,
                requirement_version_id=item.requirement_version_id,
                ordinal=ordinal,
            ))
        for ordinal, evidence_id in enumerate(draft.evidence_ids, 1):
            session.execute(insert(SolutionSectionEvidenceRefRow).values(
                solution_section_version_id=version_id,
                solution_section_id=draft.solution_section_id,
                project_id=draft.project_id,
                evidence_id=evidence_id,
                ordinal=ordinal,
            ))
        session.execute(insert(SolutionSectionVersionCreateResultRow).values(
            solution_section_version_id=version_id,
            solution_section_id=draft.solution_section_id,
            project_id=draft.project_id,
            version_no=proof.base.next_version_no,
            title=draft.title,
            content_document_version_ref=draft.content_document_version_ref,
            content_artifact_ref=None,
            content_fingerprint=proof.content_fingerprint,
            assumptions=assumptions, exclusions=exclusions,
            supersedes_version_ref=proof.base.supersedes_version_id,
            created_by=actor_id, created_at=created_at,
            **counts,
        ))
        return SectionVersionInitialView(
            version_id, draft.solution_section_id, draft.project_id,
            proof.base.next_version_no, draft.title,
            draft.content_document_version_ref, proof.content_fingerprint,
            draft.requirement_refs, draft.evidence_ids,
            tuple(assumptions), tuple(exclusions),
            proof.base.supersedes_version_id, actor_id, created_at,
        )

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> SectionVersionInitialView | None:
        session = _session(transaction)
        row = session.execute(select(SolutionSectionVersionCreateResultRow).where(
            SolutionSectionVersionCreateResultRow.solution_section_version_id == version_id,
            SolutionSectionVersionCreateResultRow.project_id == project_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        requirements = session.execute(select(SolutionSectionRequirementRefRow).where(
            SolutionSectionRequirementRefRow.solution_section_version_id == version_id,
            SolutionSectionRequirementRefRow.solution_section_id == row.solution_section_id,
            SolutionSectionRequirementRefRow.project_id == project_id,
        ).order_by(SolutionSectionRequirementRefRow.ordinal)).scalars().all()
        evidence = session.execute(select(SolutionSectionEvidenceRefRow).where(
            SolutionSectionEvidenceRefRow.solution_section_version_id == version_id,
            SolutionSectionEvidenceRefRow.solution_section_id == row.solution_section_id,
            SolutionSectionEvidenceRefRow.project_id == project_id,
        ).order_by(SolutionSectionEvidenceRefRow.ordinal)).scalars().all()
        if (len(requirements) != row.declared_requirement_count
                or len(evidence) != row.declared_evidence_count
                or any(item.ordinal != ordinal
                       for ordinal, item in enumerate(requirements, 1))
                or any(item.ordinal != ordinal
                       for ordinal, item in enumerate(evidence, 1))):
            raise RuntimeError("SectionVersion first result references are incomplete")
        return SectionVersionInitialView(
            row.solution_section_version_id, row.solution_section_id,
            row.project_id, row.version_no, row.title,
            row.content_document_version_ref, row.content_fingerprint,
            tuple(SectionRequirementRef(item.requirement_id,
                                        item.requirement_version_id)
                  for item in requirements),
            tuple(item.evidence_id for item in evidence),
            tuple(row.assumptions), tuple(row.exclusions),
            row.supersedes_version_ref, row.created_by, row.created_at,
        )
