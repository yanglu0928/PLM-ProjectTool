"""Atomic persistence of a fully validated immutable PlanVersion snapshot."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionCreatedView,
)
from plm_assistant.modules.plan.application.plan_version_input import (
    FixedVersionRef, PlanExclusionInput, ValidatedPlanVersionDraft,
)
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanMilestoneItemRefRow, PlanMilestoneRow, PlanRow, PlanVersionExclusionRow,
    PlanVersionRow, PlanWbsConditionRow, PlanWbsDependencyRow,
    PlanWbsEvidenceRefRow, PlanWbsItemRow, PlanWbsPrototypeRefRow,
    PlanWbsRequirementRefRow, PlanWbsSolutionRefRow, PlanWbsSupportRoleRow,
)
from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active PlanVersion transaction required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active PlanVersion transaction required")
    return session


class SqlAlchemyPlanVersionCreateRepository:
    def create(self, transaction: object, *, actor_id: uuid.UUID,
               project_id: uuid.UUID, plan_id: uuid.UUID,
               draft: ValidatedPlanVersionDraft) -> PlanVersionCreatedView:
        session = _session(transaction)
        plan = session.execute(select(PlanRow).where(
            PlanRow.plan_id == plan_id, PlanRow.project_id == project_id,
        ).with_for_update(of=PlanRow)).scalar_one_or_none()
        if plan is None or plan.plan_state != "ACTIVE":
            raise RuntimeError("Plan is unavailable")

        version_no = session.execute(select(func.coalesce(
            func.max(PlanVersionRow.version_no), 0) + 1).where(
                PlanVersionRow.plan_id == plan_id,
                PlanVersionRow.project_id == project_id,
            )).scalar_one()
        plan_version_id = uuid.UUID(new_uuid7())
        created_at = session.execute(insert(PlanVersionRow).values(
            plan_version_id=plan_version_id, plan_id=plan_id,
            project_id=project_id, version_no=version_no,
            calendar_ref=draft.input.calendar_ref, version_state="DRAFT",
            supersedes_version_ref=None, review_ref=None, review_round_ref=None,
            created_by=actor_id,
        ).returning(PlanVersionRow.created_at)).scalar_one()

        wbs = draft.input.wbs_items
        item_context = {
            item.wbs_item_id: {
                "wbs_item_id": item.wbs_item_id,
                "plan_version_id": plan_version_id,
                "plan_id": plan_id, "project_id": project_id,
            }
            for item in wbs
        }
        session.execute(insert(PlanWbsItemRow).values([{
            **item_context[item.wbs_item_id],
            "parent_item_id": item.parent_item_id,
            "wbs_code": item.wbs_code, "name": item.name,
            "level": item.level,
            "ordinal": index,
            "item_state": item.item_state,
            "category_code": item.category,
            "owner_project_member_id": item.owner_project_member_id,
            "planned_start_date": item.planned_start,
            "planned_finish_date": item.planned_finish,
            "planned_duration_minutes": item.duration_minutes,
            "actual_start_date": item.actual_start,
            "actual_finish_date": item.actual_finish,
            "risk_summary": item.risk,
            "explicit_exclusion_reason": item.explicit_exclusion,
        } for index, item in enumerate(wbs, start=1)]))

        roles = [{**item_context[item.wbs_item_id], "support_role": role,
                  "ordinal": ordinal}
                 for item in wbs
                 for ordinal, role in enumerate(item.support_role_refs, start=1)]
        if roles:
            session.execute(insert(PlanWbsSupportRoleRow).values(roles))
        conditions = [
            {**item_context[item.wbs_item_id], "condition_kind": kind,
             "ordinal": ordinal, "condition_text": text}
            for item in wbs
            for kind, values in (("ENTRY", item.entry_conditions),
                                 ("ACCEPTANCE", item.acceptance_criteria))
            for ordinal, text in enumerate(values, start=1)
        ]
        if conditions:
            session.execute(insert(PlanWbsConditionRow).values(conditions))

        dependencies = [{
            "dependency_id": item.dependency_id, "plan_version_id": plan_version_id,
            "plan_id": plan_id, "project_id": project_id,
            "predecessor_item_id": item.predecessor_item_id,
            "successor_item_id": item.successor_item_id,
            "dependency_type": item.dependency_type, "lag": item.lag,
            "lag_unit": item.lag_unit, "lag_reason": item.lag_reason,
        } for item in draft.input.dependencies]
        if dependencies:
            session.execute(insert(PlanWbsDependencyRow).values(dependencies))

        exclusions = [self._exclusion(
            item, ordinal=index, plan_version_id=plan_version_id,
            plan_id=plan_id, project_id=project_id)
            for index, item in enumerate(draft.input.exclusions, start=1)]
        if exclusions:
            session.execute(insert(PlanVersionExclusionRow).values(exclusions))

        for item in wbs:
            for kind, refs in (("REQUIREMENT", item.requirement_refs),
                               ("SOLUTION", item.solution_refs),
                               ("PROTOTYPE", item.prototype_refs),
                               ("EVIDENCE", item.evidence_refs)):
                rows = self._item_refs(kind, item.wbs_item_id, refs,
                                       plan_version_id, plan_id, project_id, session)
                if not rows:
                    continue
                model = {
                    "REQUIREMENT": PlanWbsRequirementRefRow,
                    "SOLUTION": PlanWbsSolutionRefRow,
                    "PROTOTYPE": PlanWbsPrototypeRefRow,
                    "EVIDENCE": PlanWbsEvidenceRefRow,
                }[kind]
                session.execute(insert(model).values(rows))

        for milestone in draft.input.milestones:
            milestone_id = uuid.UUID(new_uuid7())
            session.execute(insert(PlanMilestoneRow).values(
                milestone_id=milestone_id, plan_version_id=plan_version_id,
                plan_id=plan_id, project_id=project_id, name=milestone.name,
                target_date=milestone.target_date, duration_days=milestone.duration_days,
                acceptance_rule=milestone.acceptance_rule,
                gate_ref=milestone.gate_ref, milestone_state="PLANNED",
            ))
            links = [{
                "milestone_id": milestone_id, "plan_version_id": plan_version_id,
                "plan_id": plan_id, "project_id": project_id,
                "wbs_item_id": item_id, "ordinal": index,
            } for index, item_id in enumerate(milestone.wbs_item_refs, start=1)]
            if links:
                session.execute(insert(PlanMilestoneItemRefRow).values(links))

        return PlanVersionCreatedView(
            plan_version_id, plan_id, project_id, version_no, "DRAFT", created_at)

    def first_result(self, transaction: object, *, plan_version_id: uuid.UUID,
                     project_id: uuid.UUID,
                     plan_id: uuid.UUID) -> PlanVersionCreatedView | None:
        row = _session(transaction).execute(select(PlanVersionRow).where(
            PlanVersionRow.plan_version_id == plan_version_id,
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_id == plan_id,
        )).scalar_one_or_none()
        if row is None or row.version_state != "DRAFT":
            return None
        return PlanVersionCreatedView(
            row.plan_version_id, row.plan_id, row.project_id,
            row.version_no, row.version_state, row.created_at)

    @staticmethod
    def _exclusion(item: PlanExclusionInput, *, ordinal: int,
                   plan_version_id: uuid.UUID, plan_id: uuid.UUID,
                   project_id: uuid.UUID) -> dict[str, object]:
        row: dict[str, object] = {
            "exclusion_id": uuid.UUID(new_uuid7()),
            "plan_version_id": plan_version_id, "plan_id": plan_id,
            "project_id": project_id, "ordinal": ordinal,
            "target_kind": item.target_kind,
            "reason": item.reason, "impact": item.impact,
        }
        if item.target_kind == "REQUIREMENT_VERSION":
            row.update(requirement_id=item.resource_id,
                       requirement_version_id=item.version_id)
        elif item.target_kind == "SOLUTION_OUTLINE_VERSION":
            row.update(solution_outline_id=item.resource_id,
                       solution_outline_version_id=item.version_id)
        elif item.target_kind == "SOLUTION_SECTION_VERSION":
            row.update(solution_section_id=item.resource_id,
                       solution_section_version_id=item.version_id)
        elif item.target_kind == "STRUCTURED_SPEC_VERSION":
            row.update(spec_series_id=item.spec_series_id,
                       structured_solution_spec_id=item.version_id,
                       spec_type=item.spec_type)
        else:
            raise ValueError("unsupported Plan exclusion target")
        return row

    @staticmethod
    def _item_refs(kind: str, item_id: uuid.UUID, refs: tuple[object, ...],
                   plan_version_id: uuid.UUID, plan_id: uuid.UUID,
                   project_id: uuid.UUID, session: Session) -> list[dict[str, object]]:
        common = {"wbs_item_id": item_id, "plan_version_id": plan_version_id,
                  "plan_id": plan_id, "project_id": project_id}
        result = []
        for ordinal, ref in enumerate(refs, start=1):
            row: dict[str, object] = {**common, "ordinal": ordinal}
            if kind == "REQUIREMENT":
                row.update(requirement_id=ref.requirement_id,
                           requirement_version_id=ref.requirement_version_id)
            elif kind == "SOLUTION":
                if ref.resource_kind == "OUTLINE":
                    row.update(source_kind="OUTLINE",
                               solution_outline_id=ref.resource_id,
                               solution_outline_version_id=ref.version_id)
                elif ref.resource_kind == "SECTION":
                    row.update(source_kind="SECTION",
                               solution_section_id=ref.resource_id,
                               solution_section_version_id=ref.version_id)
                elif ref.resource_kind == "STRUCTURED_SPEC":
                    if ref.resource_id != ref.spec_series_id:
                        raise ValueError("Structured Spec resource must bind its series")
                    row.update(source_kind="STRUCTURED_SPEC",
                               spec_series_id=ref.spec_series_id,
                               structured_solution_spec_id=ref.version_id,
                               spec_type=ref.spec_type)
                else:
                    raise ValueError("unsupported Plan Solution reference")
            elif kind == "PROTOTYPE":
                row.update(prototype_id=ref.resource_id,
                           prototype_version_id=ref.version_id)
            elif kind == "EVIDENCE":
                evidence = session.execute(select(EvidenceRow).where(
                    EvidenceRow.evidence_id == ref,
                    ((EvidenceRow.scope == "GLOBAL") & EvidenceRow.project_id.is_(None))
                    | ((EvidenceRow.scope == "PROJECT")
                       & (EvidenceRow.project_id == project_id)),
                ).with_for_update(read=True, of=EvidenceRow)).scalar_one_or_none()
                if evidence is None or evidence.eligibility_state != "ELIGIBLE":
                    raise ValueError("Evidence source is unavailable")
                row.update(evidence_id=ref, source_scope=evidence.scope,
                           source_project_id=evidence.project_id)
            else:
                raise ValueError("unsupported Plan reference kind")
            result.append(row)
        return result
