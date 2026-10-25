"""Bounded SQL keyset read of one immutable PlanVersion's WBS items."""

from __future__ import annotations

import uuid

from sqlalchemy import select, tuple_

from plm_assistant.modules.plan.application.list_plan_version_wbs import (
    PlanVersionWbsItemView, PlanVersionWbsPage,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanMilestoneItemRefRow, PlanMilestoneRow, PlanRow, PlanVersionRow,
    PlanWbsConditionRow, PlanWbsEvidenceRefRow,
    PlanWbsItemRow, PlanWbsPrototypeRefRow, PlanWbsRequirementRefRow,
    PlanWbsSolutionRefRow, PlanWbsSupportRoleRow,
)


def _uuid(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None


def _date(value) -> str | None:
    return value.isoformat() if value is not None else None


class SqlAlchemyPlanVersionWbsReadRepository:
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID, plan_version_id: uuid.UUID,
                     after_ordinal: int | None, after_wbs_item_id: uuid.UUID | None,
                     limit: int) -> PlanVersionWbsPage | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, plan_id, plan_version_id))
                or ((after_ordinal is None) != (after_wbs_item_id is None))
                or (after_ordinal is not None and (
                    type(after_ordinal) is not int or after_ordinal < 1
                    or type(after_wbs_item_id) is not uuid.UUID
                    or after_wbs_item_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise ValueError("invalid PlanVersion WBS page query")
        session = _session(transaction)
        root_id = session.execute(select(PlanVersionRow.plan_version_id).join(
            PlanRow, (PlanRow.plan_id == PlanVersionRow.plan_id)
            & (PlanRow.project_id == PlanVersionRow.project_id),
        ).where(
            PlanVersionRow.plan_version_id == plan_version_id,
            PlanVersionRow.plan_id == plan_id,
            PlanVersionRow.project_id == project_id,
            PlanRow.plan_id == plan_id, PlanRow.project_id == project_id,
        ).with_for_update(read=True, of=PlanVersionRow)).scalar_one_or_none()
        if root_id is None:
            return None

        statement = select(PlanWbsItemRow).where(
            PlanWbsItemRow.project_id == project_id,
            PlanWbsItemRow.plan_id == plan_id,
            PlanWbsItemRow.plan_version_id == plan_version_id,
        )
        if after_ordinal is not None:
            statement = statement.where(tuple_(
                PlanWbsItemRow.ordinal, PlanWbsItemRow.wbs_item_id,
            ) > tuple_(after_ordinal, after_wbs_item_id))
        rows = tuple(session.execute(statement.order_by(
            PlanWbsItemRow.ordinal, PlanWbsItemRow.wbs_item_id,
        ).limit(limit + 1)).scalars())
        has_more = len(rows) > limit
        selected = rows[:limit]
        item_ids = tuple(row.wbs_item_id for row in selected)
        roles: dict[uuid.UUID, list[str]] = {item_id: [] for item_id in item_ids}
        conditions: dict[uuid.UUID, dict[str, list[str]]] = {
            item_id: {"ENTRY": [], "ACCEPTANCE": []} for item_id in item_ids}
        requirements: dict[uuid.UUID, list[dict[str, str]]] = {
            item_id: [] for item_id in item_ids}
        solutions: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        prototypes: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        evidence: dict[uuid.UUID, list[str]] = {item_id: [] for item_id in item_ids}
        if item_ids:
            for row in session.execute(select(PlanWbsSupportRoleRow).where(
                    PlanWbsSupportRoleRow.project_id == project_id,
                    PlanWbsSupportRoleRow.plan_id == plan_id,
                    PlanWbsSupportRoleRow.plan_version_id == plan_version_id,
                    PlanWbsSupportRoleRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsSupportRoleRow.wbs_item_id,
                       PlanWbsSupportRoleRow.ordinal)).scalars():
                roles[row.wbs_item_id].append(row.support_role)
            for row in session.execute(select(PlanWbsConditionRow).where(
                    PlanWbsConditionRow.project_id == project_id,
                    PlanWbsConditionRow.plan_id == plan_id,
                    PlanWbsConditionRow.plan_version_id == plan_version_id,
                    PlanWbsConditionRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsConditionRow.wbs_item_id,
                       PlanWbsConditionRow.condition_kind,
                       PlanWbsConditionRow.ordinal)).scalars():
                conditions[row.wbs_item_id][row.condition_kind].append(row.condition_text)
            for row in session.execute(select(PlanWbsRequirementRefRow).where(
                    PlanWbsRequirementRefRow.project_id == project_id,
                    PlanWbsRequirementRefRow.plan_id == plan_id,
                    PlanWbsRequirementRefRow.plan_version_id == plan_version_id,
                    PlanWbsRequirementRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsRequirementRefRow.wbs_item_id,
                       PlanWbsRequirementRefRow.ordinal)).scalars():
                requirements[row.wbs_item_id].append({
                    "requirement_id": str(row.requirement_id),
                    "requirement_version_id": str(row.requirement_version_id),
                })
            for row in session.execute(select(PlanWbsSolutionRefRow).where(
                    PlanWbsSolutionRefRow.project_id == project_id,
                    PlanWbsSolutionRefRow.plan_id == plan_id,
                    PlanWbsSolutionRefRow.plan_version_id == plan_version_id,
                    PlanWbsSolutionRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsSolutionRefRow.wbs_item_id,
                       PlanWbsSolutionRefRow.ordinal)).scalars():
                solutions[row.wbs_item_id].append(self._solution_ref(row))
            for row in session.execute(select(PlanWbsPrototypeRefRow).where(
                    PlanWbsPrototypeRefRow.project_id == project_id,
                    PlanWbsPrototypeRefRow.plan_id == plan_id,
                    PlanWbsPrototypeRefRow.plan_version_id == plan_version_id,
                    PlanWbsPrototypeRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsPrototypeRefRow.wbs_item_id,
                       PlanWbsPrototypeRefRow.ordinal)).scalars():
                prototypes[row.wbs_item_id].append({
                    "resource_kind": "PROTOTYPE",
                    "resource_id": str(row.prototype_id),
                    "version_id": str(row.prototype_version_id),
                    "spec_series_id": None, "spec_type": None,
                })
            for row in session.execute(select(PlanWbsEvidenceRefRow).where(
                    PlanWbsEvidenceRefRow.project_id == project_id,
                    PlanWbsEvidenceRefRow.plan_id == plan_id,
                    PlanWbsEvidenceRefRow.plan_version_id == plan_version_id,
                    PlanWbsEvidenceRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsEvidenceRefRow.wbs_item_id,
                       PlanWbsEvidenceRefRow.ordinal)).scalars():
                evidence[row.wbs_item_id].append(str(row.evidence_id))

        milestone_refs: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        if item_ids:
            links = tuple(session.execute(select(
                PlanMilestoneItemRefRow.wbs_item_id,
                PlanMilestoneItemRefRow.milestone_id,
            ).where(
                PlanMilestoneItemRefRow.project_id == project_id,
                PlanMilestoneItemRefRow.plan_id == plan_id,
                PlanMilestoneItemRefRow.plan_version_id == plan_version_id,
                PlanMilestoneItemRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanMilestoneItemRefRow.wbs_item_id,
                       PlanMilestoneItemRefRow.ordinal)).all())
            milestone_ids = tuple({row.milestone_id for row in links})
            milestone_rows = tuple(session.execute(select(PlanMilestoneRow).where(
                PlanMilestoneRow.project_id == project_id,
                PlanMilestoneRow.plan_id == plan_id,
                PlanMilestoneRow.plan_version_id == plan_version_id,
                PlanMilestoneRow.milestone_id.in_(milestone_ids),
            )).scalars()) if milestone_ids else ()
            milestone_by_id = {row.milestone_id: row for row in milestone_rows}
            for link in links:
                milestone = milestone_by_id.get(link.milestone_id)
                if milestone is not None:
                    milestone_refs[link.wbs_item_id].append({
                        "name": milestone.name,
                        "target_date": milestone.target_date.isoformat(),
                    })

        result = []
        for row in selected:
            data = {
                "wbs_item_id": str(row.wbs_item_id),
                "parent_item_id": _uuid(row.parent_item_id),
                "wbs_code": row.wbs_code, "name": row.name, "level": row.level,
                "category": row.category_code,
                "owner_ref": _uuid(row.owner_project_member_id),
                "support_role_refs": roles[row.wbs_item_id],
                "planned_start": _date(row.planned_start_date),
                "planned_finish": _date(row.planned_finish_date),
                "duration_minutes": row.planned_duration_minutes,
                "actual_start": _date(row.actual_start_date),
                "actual_finish": _date(row.actual_finish_date),
                "item_state": row.item_state,
                "entry_conditions": conditions[row.wbs_item_id]["ENTRY"],
                "acceptance_criteria": conditions[row.wbs_item_id]["ACCEPTANCE"],
                "requirement_refs": requirements[row.wbs_item_id],
                "solution_refs": solutions[row.wbs_item_id],
                "prototype_refs": prototypes[row.wbs_item_id],
                "evidence_refs": evidence[row.wbs_item_id],
                "output_refs": [], "risk": row.risk_summary,
                "explicit_exclusion": row.explicit_exclusion_reason,
                "milestone_refs": milestone_refs[row.wbs_item_id],
            }
            result.append(PlanVersionWbsItemView(row.wbs_item_id, row.ordinal, data))
        last = result[-1] if result else None
        return PlanVersionWbsPage(
            plan_id, plan_version_id, project_id, tuple(result),
            last.ordinal if has_more and last else None,
            last.wbs_item_id if has_more and last else None,
            has_more,
        )

    @staticmethod
    def _solution_ref(row: PlanWbsSolutionRefRow) -> dict[str, object]:
        if row.source_kind == "OUTLINE":
            resource_id, version_id = row.solution_outline_id, row.solution_outline_version_id
            series_id, spec_type = None, None
        elif row.source_kind == "SECTION":
            resource_id, version_id = row.solution_section_id, row.solution_section_version_id
            series_id, spec_type = None, None
        else:
            resource_id, version_id = row.spec_series_id, row.structured_solution_spec_id
            series_id, spec_type = row.spec_series_id, row.spec_type
        return {
            "resource_kind": row.source_kind,
            "resource_id": str(resource_id), "version_id": str(version_id),
            "spec_series_id": _uuid(series_id), "spec_type": spec_type,
        }
