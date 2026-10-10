"""SQLAlchemy persistence for complete immutable RequirementVersion drafts."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, insert, select, text, update

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, CreatedRequirementVersion,
    RequirementVersionCreateError, RequirementVersionRootLock,
)

from .identity_create_repository import _session
from .orm import (
    RequirementAcceptanceCriterionRow, RequirementAssessmentEvidenceRefRow,
    RequirementAssumptionRow, RequirementCapabilityAssessmentRow,
    RequirementDependencyRow, RequirementExclusionRow, RequirementRow,
    RequirementSourceEvidenceRefRow, RequirementSourceRow,
    RequirementVersionAITaskRefRow, RequirementVersionCreateResultRow,
    RequirementVersionRow,
)


class SqlAlchemyRequirementVersionCreateRepository:
    def lock_requirement(self, transaction: object, *, project_id: uuid.UUID,
                         requirement_id: uuid.UUID) -> RequirementVersionRootLock | None:
        session = _session(transaction)
        root = session.execute(select(RequirementRow).where(
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_id == requirement_id,
        ).with_for_update(of=RequirementRow)
          .execution_options(populate_existing=True)).scalar_one_or_none()
        if root is None:
            return None
        latest = session.execute(select(
            RequirementVersionRow.requirement_version_id,
            RequirementVersionRow.version_no,
        ).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
        ).order_by(RequirementVersionRow.version_no.desc()).limit(1)
          .execution_options(autoflush=False)).one_or_none()
        return RequirementVersionRootLock(
            root.requirement_id, root.project_id, root.requirement_state,
            root.lock_version, 0 if latest is None else latest.version_no,
            None if latest is None else latest.requirement_version_id,
        )

    def create(self, transaction: object, *, root: RequirementVersionRootLock,
               requirement_version_id: uuid.UUID, actor_id: uuid.UUID,
               content_fingerprint: bytes,
               command: CreateRequirementVersion) -> CreatedRequirementVersion:
        session = _session(transaction)
        changed = session.execute(update(RequirementRow).where(
            RequirementRow.requirement_id == root.requirement_id,
            RequirementRow.project_id == root.project_id,
            RequirementRow.requirement_state == "ACTIVE",
            RequirementRow.lock_version == root.lock_version,
            ~exists(select(1).where(
                RequirementVersionRow.requirement_id == root.requirement_id,
                RequirementVersionRow.project_id == root.project_id,
                RequirementVersionRow.version_state == "IN_REVIEW",
            )),
        ).values(updated_by=actor_id, updated_at=text("statement_timestamp()"),
                 lock_version=RequirementRow.lock_version + 1)
          .returning(RequirementRow.lock_version)).scalar_one_or_none()
        if changed != root.lock_version + 1:
            raise RequirementVersionCreateError("CONFLICT_VERSION")
        session.execute(insert(RequirementVersionRow).values(
            requirement_version_id=requirement_version_id,
            requirement_id=root.requirement_id, project_id=root.project_id,
            version_no=root.highest_version_no + 1, version_state="DRAFT",
            title=command.title, statement=command.statement,
            rationale=command.rationale, domain_name=command.domain_name,
            priority=command.priority, risk=command.risk,
            requirement_classification=command.classification,
            content_fingerprint=content_fingerprint,
            declared_source_count=len(command.sources),
            declared_acceptance_count=len(command.acceptance_criteria),
            declared_capability_count=len(command.capability_assessments),
            declared_assumption_count=len(command.assumptions),
            declared_exclusion_count=len(command.exclusions),
            declared_dependency_count=len(command.dependencies),
            declared_ai_task_count=len(command.ai_task_refs),
            supersedes_version_ref=root.latest_version_id,
            review_ref=None, review_round_ref=None, created_by=actor_id,
        ))
        for ordinal, source in enumerate(command.sources):
            source_id = uuid.UUID(new_uuid7())
            session.execute(insert(RequirementSourceRow).values(
                requirement_source_id=source_id,
                requirement_version_id=requirement_version_id,
                requirement_id=root.requirement_id, project_id=root.project_id,
                ordinal=ordinal, source_type=source.source_type,
                source_object_id=source.source_object_id,
                source_version_ref=source.source_version_ref,
            ))
            for evidence_ordinal, evidence_id in enumerate(source.evidence_refs):
                session.execute(insert(RequirementSourceEvidenceRefRow).values(
                    source_evidence_ref_id=uuid.UUID(new_uuid7()),
                    requirement_source_id=source_id,
                    requirement_version_id=requirement_version_id,
                    requirement_id=root.requirement_id, project_id=root.project_id,
                    evidence_id=evidence_id, ordinal=evidence_ordinal,
                ))
        for ordinal, item in enumerate(command.acceptance_criteria):
            session.execute(insert(RequirementAcceptanceCriterionRow).values(
                acceptance_criterion_id=uuid.UUID(new_uuid7()),
                requirement_version_id=requirement_version_id,
                requirement_id=root.requirement_id, project_id=root.project_id,
                ordinal=ordinal, observable_result=item.observable_result,
                verification_method=item.verification_method,
                required_data=item.required_data,
                required_environment=item.required_environment,
                evidence_requirement=item.evidence_requirement,
            ))
        for ordinal, item in enumerate(command.capability_assessments):
            assessment_id = uuid.UUID(new_uuid7())
            session.execute(insert(RequirementCapabilityAssessmentRow).values(
                capability_assessment_id=assessment_id,
                requirement_version_id=requirement_version_id,
                requirement_id=root.requirement_id, project_id=root.project_id,
                ordinal=ordinal, baseline_version_id=item.baseline_version_id,
                capability_item_id=item.capability_item_id,
                match_type=item.match_type, fit_gap=item.fit_gap,
                constraints_text=item.constraints_text,
                assessor_kind=item.assessor_kind,
                assessed_by=actor_id if item.assessor_kind == "HUMAN" else None,
                assessed_at=text("statement_timestamp()"),
                confirmation_state=item.confirmation_state,
            ))
            for evidence_ordinal, ref in enumerate(item.evidence_refs):
                session.execute(insert(RequirementAssessmentEvidenceRefRow).values(
                    assessment_evidence_ref_id=uuid.UUID(new_uuid7()),
                    capability_assessment_id=assessment_id,
                    requirement_version_id=requirement_version_id,
                    requirement_id=root.requirement_id, project_id=root.project_id,
                    evidence_id=ref.evidence_id, evidence_role=ref.evidence_role,
                    ordinal=evidence_ordinal,
                ))
        for model, column, values in (
            (RequirementAssumptionRow, "assumption_text", command.assumptions),
            (RequirementExclusionRow, "exclusion_text", command.exclusions),
            (RequirementDependencyRow, "dependency_text", command.dependencies),
        ):
            for ordinal, value in enumerate(values):
                session.execute(insert(model).values(
                    requirement_version_id=requirement_version_id,
                    requirement_id=root.requirement_id, project_id=root.project_id,
                    ordinal=ordinal, **{column: value},
                ))
        for ordinal, task_id in enumerate(command.ai_task_refs):
            session.execute(insert(RequirementVersionAITaskRefRow).values(
                ai_task_ref_id=uuid.UUID(new_uuid7()),
                requirement_version_id=requirement_version_id,
                requirement_id=root.requirement_id, project_id=root.project_id,
                ai_task_id=task_id, task_scope="PROJECT", ordinal=ordinal,
            ))
        session.execute(insert(RequirementVersionCreateResultRow).values(
            requirement_version_id=requirement_version_id,
            requirement_id=root.requirement_id, project_id=root.project_id,
            actor_id=actor_id, expected_lock_version=root.lock_version,
            lock_version=root.lock_version + 1,
            content_fingerprint=content_fingerprint,
        ))
        row = session.execute(select(RequirementVersionRow).where(
            RequirementVersionRow.requirement_version_id == requirement_version_id,
        )).scalar_one()
        return self._view(row, root.lock_version)

    def initial_view(self, transaction: object, *, project_id: uuid.UUID,
                     requirement_id: uuid.UUID,
                     requirement_version_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedRequirementVersion | None:
        row = _session(transaction).execute(select(
            RequirementVersionRow, RequirementVersionCreateResultRow,
        ).join(RequirementVersionCreateResultRow,
            RequirementVersionCreateResultRow.requirement_version_id
            == RequirementVersionRow.requirement_version_id).where(
            RequirementVersionRow.requirement_version_id == requirement_version_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.project_id == project_id,
            RequirementVersionCreateResultRow.expected_lock_version
            == expected_lock_version,
        ).execution_options(populate_existing=True)).one_or_none()
        return None if row is None else self._view(row[0], row[1].expected_lock_version)

    @staticmethod
    def _view(row: RequirementVersionRow, expected: int) -> CreatedRequirementVersion:
        return CreatedRequirementVersion(
            row.requirement_version_id, row.requirement_id, row.project_id,
            row.version_no, row.version_state, bytes(row.content_fingerprint),
            row.supersedes_version_ref, row.created_by, row.created_at,
            expected, expected + 1,
        )
