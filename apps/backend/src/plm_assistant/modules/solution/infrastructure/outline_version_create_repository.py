"""Persist a fixed OutlineVersion collection and first result in one transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.create_outline_version import (
    OutlineVersionInitialView,
)
from plm_assistant.modules.solution.application.prove_outline_version_input import (
    ProvenOutlineVersionInput,
)

from .orm import (
    SolutionOutlineRequirementRefRow,
    SolutionOutlineReferenceRefRow,
    SolutionOutlineSectionRow,
    SolutionOutlineVersionCreateResultRow,
    SolutionOutlineVersionRow,
)
from .reference_deidentification_repository import _session


class SqlAlchemyOutlineVersionCreateRepository:
    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenOutlineVersionInput) -> OutlineVersionInitialView:
        session = _session(transaction)
        draft = proof.draft
        missing = draft.missing_declarations()
        conflicts = draft.conflict_declarations()
        counts = dict(
            declared_section_count=len(draft.section_ids),
            declared_requirement_count=len(draft.requirement_refs),
            declared_reference_count=len(draft.reference_refs),
        )
        created_at = session.execute(insert(SolutionOutlineVersionRow).values(
            solution_outline_version_id=version_id,
            solution_outline_id=draft.solution_outline_id,
            project_id=draft.project_id,
            version_no=proof.next_version_no,
            version_state="DRAFT",
            content_fingerprint=proof.content_fingerprint,
            missing_declarations=missing,
            conflict_declarations=conflicts,
            supersedes_version_ref=proof.supersedes_version_id,
            review_ref=None, review_round_ref=None,
            created_by=actor_id,
            **counts,
        ).returning(SolutionOutlineVersionRow.created_at)).scalar_one()
        for ordinal, section_id in enumerate(draft.section_ids, 1):
            session.execute(insert(SolutionOutlineSectionRow).values(
                solution_outline_version_id=version_id,
                solution_outline_id=draft.solution_outline_id,
                project_id=draft.project_id,
                solution_section_id=section_id,
                ordinal=ordinal,
            ))
        for ordinal, item in enumerate(draft.requirement_refs, 1):
            session.execute(insert(SolutionOutlineRequirementRefRow).values(
                solution_outline_version_id=version_id,
                solution_outline_id=draft.solution_outline_id,
                project_id=draft.project_id,
                requirement_id=item.requirement_id,
                requirement_version_id=item.requirement_version_id,
                ordinal=ordinal,
            ))
        for ordinal, item in enumerate(draft.reference_refs, 1):
            session.execute(insert(SolutionOutlineReferenceRefRow).values(
                solution_outline_version_id=version_id,
                solution_outline_id=draft.solution_outline_id,
                project_id=draft.project_id,
                reference_solution_id=item.reference_solution_id,
                reference_version_id=item.reference_version_id,
                reference_scope=item.scope,
                source_project_id=draft.project_id if item.scope == "PROJECT" else None,
                ordinal=ordinal,
            ))
        session.execute(insert(SolutionOutlineVersionCreateResultRow).values(
            solution_outline_version_id=version_id,
            solution_outline_id=draft.solution_outline_id,
            project_id=draft.project_id,
            version_no=proof.next_version_no,
            content_fingerprint=proof.content_fingerprint,
            missing_declarations=missing,
            conflict_declarations=conflicts,
            supersedes_version_ref=proof.supersedes_version_id,
            created_by=actor_id,
            created_at=created_at,
            **counts,
        ))
        return OutlineVersionInitialView(
            version_id, draft.solution_outline_id, draft.project_id,
            proof.next_version_no, proof.content_fingerprint,
            tuple(missing), tuple(conflicts),
            len(draft.section_ids), len(draft.requirement_refs),
            len(draft.reference_refs), proof.supersedes_version_id,
            actor_id, created_at,
        )

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> OutlineVersionInitialView | None:
        row = _session(transaction).execute(
            select(SolutionOutlineVersionCreateResultRow).where(
                SolutionOutlineVersionCreateResultRow.solution_outline_version_id == version_id,
                SolutionOutlineVersionCreateResultRow.project_id == project_id,
            )).scalar_one_or_none()
        if row is None:
            return None
        return OutlineVersionInitialView(
            row.solution_outline_version_id, row.solution_outline_id,
            row.project_id, row.version_no, row.content_fingerprint,
            tuple(row.missing_declarations), tuple(row.conflict_declarations),
            row.declared_section_count, row.declared_requirement_count,
            row.declared_reference_count, row.supersedes_version_ref,
            row.created_by, row.created_at,
        )
