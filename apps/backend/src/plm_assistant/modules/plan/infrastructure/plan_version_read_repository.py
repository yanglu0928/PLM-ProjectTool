"""Project-scoped reconstruction of an immutable PlanVersion snapshot."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionSnapshotView,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanMilestoneItemRefRow, PlanMilestoneRow, PlanRow, PlanVersionExclusionRow,
    PlanVersionRow, PlanWbsConditionRow, PlanWbsDependencyRow,
    PlanWbsEvidenceRefRow, PlanWbsItemRow, PlanWbsPrototypeRefRow,
    PlanWbsRequirementRefRow, PlanWbsSolutionRefRow, PlanWbsSupportRoleRow,
)


def _uuid(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None


def _date(value) -> str | None:
    return value.isoformat() if value is not None else None


class SqlAlchemyPlanVersionReadRepository:
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID,
                    plan_version_id: uuid.UUID) -> PlanVersionSnapshotView | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, plan_id, plan_version_id)):
            return None
        session = _session(transaction)
        root = session.execute(select(PlanVersionRow).join(
            PlanRow, (PlanRow.plan_id == PlanVersionRow.plan_id)
            & (PlanRow.project_id == PlanVersionRow.project_id),
        ).where(
            PlanRow.project_id == project_id,
            PlanRow.plan_id == plan_id,
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_id == plan_id,
            PlanVersionRow.plan_version_id == plan_version_id,
        ).with_for_update(read=True, of=PlanVersionRow)).scalar_one_or_none()
        if root is None:
            return None

        scope = (
            PlanWbsItemRow.project_id == project_id,
            PlanWbsItemRow.plan_id == plan_id,
            PlanWbsItemRow.plan_version_id == plan_version_id,
        )
        items = tuple(session.execute(select(PlanWbsItemRow).where(*scope).order_by(
            PlanWbsItemRow.ordinal, PlanWbsItemRow.wbs_item_id,
        )).scalars())
        item_ids = tuple(item.wbs_item_id for item in items)
        roles_by_item: dict[uuid.UUID, list[str]] = {item_id: [] for item_id in item_ids}
        conditions_by_item: dict[uuid.UUID, dict[str, list[str]]] = {
            item_id: {"ENTRY": [], "ACCEPTANCE": []} for item_id in item_ids}
        solution_by_item: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        requirement_by_item: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        prototype_by_item: dict[uuid.UUID, list[dict[str, object]]] = {
            item_id: [] for item_id in item_ids}
        evidence_by_item: dict[uuid.UUID, list[str]] = {
            item_id: [] for item_id in item_ids}

        if item_ids:
            for row in session.execute(select(PlanWbsSupportRoleRow).where(
                    PlanWbsSupportRoleRow.project_id == project_id,
                    PlanWbsSupportRoleRow.plan_id == plan_id,
                    PlanWbsSupportRoleRow.plan_version_id == plan_version_id,
                    PlanWbsSupportRoleRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsSupportRoleRow.wbs_item_id,
                       PlanWbsSupportRoleRow.ordinal)).scalars():
                roles_by_item[row.wbs_item_id].append(row.support_role)

            for row in session.execute(select(PlanWbsConditionRow).where(
                    PlanWbsConditionRow.project_id == project_id,
                    PlanWbsConditionRow.plan_id == plan_id,
                    PlanWbsConditionRow.plan_version_id == plan_version_id,
                    PlanWbsConditionRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsConditionRow.wbs_item_id,
                       PlanWbsConditionRow.condition_kind,
                       PlanWbsConditionRow.ordinal)).scalars():
                conditions_by_item[row.wbs_item_id][row.condition_kind].append(
                    row.condition_text)

            for row in session.execute(select(PlanWbsRequirementRefRow).where(
                    PlanWbsRequirementRefRow.project_id == project_id,
                    PlanWbsRequirementRefRow.plan_id == plan_id,
                    PlanWbsRequirementRefRow.plan_version_id == plan_version_id,
                    PlanWbsRequirementRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsRequirementRefRow.wbs_item_id,
                       PlanWbsRequirementRefRow.ordinal)).scalars():
                requirement_by_item[row.wbs_item_id].append({
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
                solution_by_item[row.wbs_item_id].append(self._solution_ref(row))

            for row in session.execute(select(PlanWbsPrototypeRefRow).where(
                    PlanWbsPrototypeRefRow.project_id == project_id,
                    PlanWbsPrototypeRefRow.plan_id == plan_id,
                    PlanWbsPrototypeRefRow.plan_version_id == plan_version_id,
                    PlanWbsPrototypeRefRow.wbs_item_id.in_(item_ids),
            ).order_by(PlanWbsPrototypeRefRow.wbs_item_id,
                       PlanWbsPrototypeRefRow.ordinal)).scalars():
                prototype_by_item[row.wbs_item_id].append({
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
                evidence_by_item[row.wbs_item_id].append(str(row.evidence_id))

        wbs_items = [{
            "wbs_item_id": str(row.wbs_item_id),
            "parent_item_id": _uuid(row.parent_item_id),
            "wbs_code": row.wbs_code, "name": row.name, "level": row.level,
            "category": row.category_code,
            "owner_ref": _uuid(row.owner_project_member_id),
            "support_role_refs": roles_by_item[row.wbs_item_id],
            "planned_start": _date(row.planned_start_date),
            "planned_finish": _date(row.planned_finish_date),
            "duration_minutes": row.planned_duration_minutes,
            "actual_start": _date(row.actual_start_date),
            "actual_finish": _date(row.actual_finish_date),
            "item_state": row.item_state,
            "entry_conditions": conditions_by_item[row.wbs_item_id]["ENTRY"],
            "acceptance_criteria": conditions_by_item[row.wbs_item_id]["ACCEPTANCE"],
            "requirement_refs": requirement_by_item[row.wbs_item_id],
            "solution_refs": solution_by_item[row.wbs_item_id],
            "prototype_refs": prototype_by_item[row.wbs_item_id],
            "evidence_refs": evidence_by_item[row.wbs_item_id],
            "output_refs": [], "risk": row.risk_summary,
            "explicit_exclusion": row.explicit_exclusion_reason,
        } for row in items]

        approved_solution_refs: list[dict[str, object]] = []
        seen_solution_refs: set[tuple[object, ...]] = set()
        for item in wbs_items:
            for ref in item["solution_refs"]:
                assert type(ref) is dict
                identity = tuple(ref[key] for key in (
                    "resource_kind", "resource_id", "version_id",
                    "spec_series_id", "spec_type"))
                if identity not in seen_solution_refs:
                    seen_solution_refs.add(identity)
                    approved_solution_refs.append(dict(ref))

        dependencies = [{
            "dependency_id": str(row.dependency_id),
            "predecessor_item_id": str(row.predecessor_item_id),
            "successor_item_id": str(row.successor_item_id),
            "dependency_type": row.dependency_type, "lag": row.lag,
            "lag_unit": row.lag_unit, "lag_reason": row.lag_reason,
        } for row in session.execute(select(PlanWbsDependencyRow).where(
            PlanWbsDependencyRow.project_id == project_id,
            PlanWbsDependencyRow.plan_id == plan_id,
            PlanWbsDependencyRow.plan_version_id == plan_version_id,
        ).order_by(PlanWbsDependencyRow.predecessor_item_id,
                   PlanWbsDependencyRow.successor_item_id,
                   PlanWbsDependencyRow.dependency_id)).scalars()]

        milestones = []
        milestone_rows = tuple(session.execute(select(PlanMilestoneRow).where(
            PlanMilestoneRow.project_id == project_id,
            PlanMilestoneRow.plan_id == plan_id,
            PlanMilestoneRow.plan_version_id == plan_version_id,
        ).order_by(PlanMilestoneRow.target_date, PlanMilestoneRow.name,
                   PlanMilestoneRow.milestone_id)).scalars())
        milestone_refs: dict[uuid.UUID, list[str]] = {
            row.milestone_id: [] for row in milestone_rows}
        milestone_ids = tuple(milestone_refs)
        if milestone_ids:
            for ref in session.execute(select(PlanMilestoneItemRefRow).where(
                    PlanMilestoneItemRefRow.project_id == project_id,
                    PlanMilestoneItemRefRow.plan_id == plan_id,
                    PlanMilestoneItemRefRow.plan_version_id == plan_version_id,
                    PlanMilestoneItemRefRow.milestone_id.in_(milestone_ids),
            ).order_by(PlanMilestoneItemRefRow.milestone_id,
                       PlanMilestoneItemRefRow.ordinal)).scalars():
                milestone_refs[ref.milestone_id].append(str(ref.wbs_item_id))
        for row in milestone_rows:
            milestones.append({
                "name": row.name, "target_date": row.target_date.isoformat(),
                "duration_days": row.duration_days,
                "acceptance_rule": row.acceptance_rule, "gate_ref": row.gate_ref,
                "wbs_item_refs": milestone_refs[row.milestone_id],
            })

        exclusions = []
        for row in session.execute(select(PlanVersionExclusionRow).where(
                PlanVersionExclusionRow.project_id == project_id,
                PlanVersionExclusionRow.plan_id == plan_id,
                PlanVersionExclusionRow.plan_version_id == plan_version_id,
        ).order_by(PlanVersionExclusionRow.ordinal)).scalars():
            if row.target_kind == "REQUIREMENT_VERSION":
                resource_id, version_id = row.requirement_id, row.requirement_version_id
            elif row.target_kind == "SOLUTION_OUTLINE_VERSION":
                resource_id, version_id = row.solution_outline_id, row.solution_outline_version_id
            elif row.target_kind == "SOLUTION_SECTION_VERSION":
                resource_id, version_id = row.solution_section_id, row.solution_section_version_id
            else:
                resource_id, version_id = row.spec_series_id, row.structured_solution_spec_id
            exclusions.append({
                "target_kind": row.target_kind,
                "resource_id": _uuid(resource_id), "version_id": _uuid(version_id),
                "reason": row.reason, "impact": row.impact,
                "spec_series_id": _uuid(row.spec_series_id),
                "spec_type": row.spec_type,
            })

        return PlanVersionSnapshotView(
            root.plan_version_id, root.plan_id, root.project_id,
            root.version_no, root.version_state, root.created_by, root.created_at,
            root.supersedes_version_ref, root.review_ref, root.review_round_ref,
            {
                "calendar_ref": root.calendar_ref,
                "approved_solution_refs": approved_solution_refs,
                "wbs_items": wbs_items,
                "dependencies": dependencies,
                "milestones": milestones,
                "exclusions": exclusions,
            },
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
