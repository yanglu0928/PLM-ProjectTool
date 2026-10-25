"""Allow PlanVersion owners to append immutable snapshots, never rewrite them.

Revision ID: 20261026_0188
Revises: 20261026_0187
"""

from __future__ import annotations

from alembic import op


revision = "20261026_0188"
down_revision = "20261026_0187"
branch_labels = None
depends_on = None

_OWNER_FUNCTIONS = {
    "guard_plan_version_foundation": "PlanVersion",
    "guard_wbs_item_foundation": "WbsItem",
    "guard_wbs_dependency_foundation": "WbsDependency",
    "guard_plan_milestone_foundation": "PlanMilestone",
    "guard_wbs_requirement_ref_foundation": "WbsRequirementRef",
    "guard_wbs_solution_ref_foundation": "WbsSolutionRef",
    "guard_wbs_evidence_ref_foundation": "WbsEvidenceRef",
    "guard_plan_snapshot_child_foundation": "PlanSnapshotChild",
}


def _install_append_only_guards() -> None:
    for function, label in _OWNER_FUNCTIONS.items():
        op.execute(f"""
CREATE OR REPLACE FUNCTION plm.{function}()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION '{label} snapshots are immutable';
END; $$;
""")


def _restore_closed_guards() -> None:
    for function, label in _OWNER_FUNCTIONS.items():
        op.execute(f"""
CREATE OR REPLACE FUNCTION plm.{function}()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '{label} Owner is not installed';
END; $$;
""")


def upgrade() -> None:
    _install_append_only_guards()


def downgrade() -> None:
    _restore_closed_guards()
