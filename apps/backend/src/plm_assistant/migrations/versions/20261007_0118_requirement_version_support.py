"""Add RequirementVersion support refs and deferred completeness closure.

Revision ID: 20261007_0118
Revises: 20261007_0117
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0118"
down_revision = "20261007_0117"
branch_labels = None
depends_on = None

_SUPPORT_TABLES = (
    "req_source_evidence_refs",
    "req_assessment_evidence_refs",
    "req_version_ai_task_refs",
)
_CLOSURE_TABLES = (
    "req_requirement_versions",
    "req_sources",
    "req_acceptance_criteria",
    "req_capability_assessments",
    "req_assumptions",
    "req_exclusions",
    "req_dependencies",
    *_SUPPORT_TABLES,
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_support()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion support Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_version_support_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion support history cannot be truncated';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_version_completeness()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  version_id uuid := CASE WHEN TG_OP='DELETE' THEN OLD.requirement_version_id
                          ELSE NEW.requirement_version_id END;
  version_row plm.req_requirement_versions%ROWTYPE;
BEGIN
  SELECT * INTO version_row FROM plm.req_requirement_versions
   WHERE requirement_version_id=version_id;
  IF NOT FOUND THEN RETURN NULL; END IF;

  IF version_row.declared_source_count<>(SELECT count(*) FROM plm.req_sources
       WHERE requirement_version_id=version_id)
     OR version_row.declared_acceptance_count<>(SELECT count(*) FROM plm.req_acceptance_criteria
       WHERE requirement_version_id=version_id)
     OR version_row.declared_capability_count<>(SELECT count(*) FROM plm.req_capability_assessments
       WHERE requirement_version_id=version_id)
     OR version_row.declared_assumption_count<>(SELECT count(*) FROM plm.req_assumptions
       WHERE requirement_version_id=version_id)
     OR version_row.declared_exclusion_count<>(SELECT count(*) FROM plm.req_exclusions
       WHERE requirement_version_id=version_id)
     OR version_row.declared_dependency_count<>(SELECT count(*) FROM plm.req_dependencies
       WHERE requirement_version_id=version_id)
     OR version_row.declared_ai_task_count<>(SELECT count(*) FROM plm.req_version_ai_task_refs
       WHERE requirement_version_id=version_id) THEN
    RAISE EXCEPTION 'RequirementVersion declared counts do not match owned collections';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES
      ('source', (SELECT count(*) FROM plm.req_sources WHERE requirement_version_id=version_id),
                 (SELECT min(ordinal) FROM plm.req_sources WHERE requirement_version_id=version_id),
                 (SELECT max(ordinal) FROM plm.req_sources WHERE requirement_version_id=version_id)),
      ('acceptance', (SELECT count(*) FROM plm.req_acceptance_criteria WHERE requirement_version_id=version_id),
                     (SELECT min(ordinal) FROM plm.req_acceptance_criteria WHERE requirement_version_id=version_id),
                     (SELECT max(ordinal) FROM plm.req_acceptance_criteria WHERE requirement_version_id=version_id)),
      ('capability', (SELECT count(*) FROM plm.req_capability_assessments WHERE requirement_version_id=version_id),
                     (SELECT min(ordinal) FROM plm.req_capability_assessments WHERE requirement_version_id=version_id),
                     (SELECT max(ordinal) FROM plm.req_capability_assessments WHERE requirement_version_id=version_id)),
      ('assumption', (SELECT count(*) FROM plm.req_assumptions WHERE requirement_version_id=version_id),
                     (SELECT min(ordinal) FROM plm.req_assumptions WHERE requirement_version_id=version_id),
                     (SELECT max(ordinal) FROM plm.req_assumptions WHERE requirement_version_id=version_id)),
      ('exclusion', (SELECT count(*) FROM plm.req_exclusions WHERE requirement_version_id=version_id),
                    (SELECT min(ordinal) FROM plm.req_exclusions WHERE requirement_version_id=version_id),
                    (SELECT max(ordinal) FROM plm.req_exclusions WHERE requirement_version_id=version_id)),
      ('dependency', (SELECT count(*) FROM plm.req_dependencies WHERE requirement_version_id=version_id),
                     (SELECT min(ordinal) FROM plm.req_dependencies WHERE requirement_version_id=version_id),
                     (SELECT max(ordinal) FROM plm.req_dependencies WHERE requirement_version_id=version_id)),
      ('ai', (SELECT count(*) FROM plm.req_version_ai_task_refs WHERE requirement_version_id=version_id),
             (SELECT min(ordinal) FROM plm.req_version_ai_task_refs WHERE requirement_version_id=version_id),
             (SELECT max(ordinal) FROM plm.req_version_ai_task_refs WHERE requirement_version_id=version_id))
    ) AS x(kind,item_count,min_ordinal,max_ordinal)
    WHERE (item_count>0 AND (min_ordinal<>0 OR max_ordinal<>item_count-1))
       OR (item_count=0 AND (min_ordinal IS NOT NULL OR max_ordinal IS NOT NULL))
  ) THEN RAISE EXCEPTION 'RequirementVersion owned ordinals are not contiguous'; END IF;

  IF EXISTS (
    SELECT 1 FROM plm.req_capability_assessments a
     WHERE a.requirement_version_id=version_id
       AND (NOT EXISTS (SELECT 1 FROM plm.req_assessment_evidence_refs r
                         WHERE r.capability_assessment_id=a.capability_assessment_id
                           AND r.evidence_role='STANDARD')
         OR NOT EXISTS (SELECT 1 FROM plm.req_assessment_evidence_refs r
                         WHERE r.capability_assessment_id=a.capability_assessment_id
                           AND r.evidence_role='PROJECT'))
  ) THEN RAISE EXCEPTION 'Requirement capability assessment requires STANDARD and PROJECT Evidence'; END IF;

  IF EXISTS (
    SELECT 1 FROM plm.req_source_evidence_refs r
      JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id
     WHERE r.requirement_version_id=version_id
       AND (e.scope<>'PROJECT' OR e.project_id<>r.project_id
            OR e.eligibility_state<>'ELIGIBLE')
  ) THEN RAISE EXCEPTION 'Requirement source Evidence is not current project eligible'; END IF;

  IF EXISTS (
    SELECT 1 FROM plm.req_sources s
     WHERE s.requirement_version_id=version_id AND s.source_type='PROJECT_EVIDENCE'
       AND NOT EXISTS (
         SELECT 1 FROM plm.req_source_evidence_refs r
          WHERE r.requirement_source_id=s.requirement_source_id
            AND r.evidence_id=s.source_object_id
       )
  ) THEN RAISE EXCEPTION 'PROJECT_EVIDENCE source requires matching Evidence reference'; END IF;

  IF EXISTS (
    SELECT 1 FROM plm.req_assessment_evidence_refs r
      JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id
     WHERE r.requirement_version_id=version_id
       AND (e.eligibility_state<>'ELIGIBLE'
         OR (r.evidence_role='STANDARD' AND (e.scope<>'GLOBAL' OR e.project_id IS NOT NULL))
         OR (r.evidence_role='PROJECT' AND (e.scope<>'PROJECT' OR e.project_id<>r.project_id)))
  ) THEN RAISE EXCEPTION 'Requirement assessment Evidence scope or eligibility is invalid'; END IF;

  IF EXISTS (
    SELECT 1 FROM plm.req_version_ai_task_refs r
      JOIN plm.ai_tasks t ON t.ai_task_id=r.ai_task_id
     WHERE r.requirement_version_id=version_id
       AND (t.task_type NOT IN ('REQUIREMENT_NORMALIZE','REQUIREMENT_MATCH')
         OR t.task_state<>'SUCCEEDED' OR t.suggestion_state<>'ACCEPTED_TO_DRAFT'
         OR t.accepted_domain_module<>'requirement'
         OR t.accepted_domain_version_id<>version_id)
  ) THEN RAISE EXCEPTION 'Requirement AI provenance is not accepted to this draft'; END IF;
  RETURN NULL;
END; $$;
"""


def _version_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["requirement_version_id", "requirement_id", "project_id"],
        ["plm.req_requirement_versions.requirement_version_id",
         "plm.req_requirement_versions.requirement_id",
         "plm.req_requirement_versions.project_id"],
        name=name, ondelete="NO ACTION",
    )


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    if not context.is_offline_mode() and op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_requirement_versions)"
    )).scalar_one():
        raise RuntimeError(
            "pre-existing RequirementVersion rows require an audited support migration"
        )
    op.create_table(
        "req_source_evidence_refs",
        sa.Column("source_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("requirement_source_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("requirement_source_id", "evidence_id",
                            name="uq_req_source_evidence__source_evidence"),
        sa.UniqueConstraint("requirement_source_id", "ordinal",
                            name="uq_req_source_evidence__source_ordinal"),
        sa.ForeignKeyConstraint(
            ["requirement_source_id", "requirement_version_id", "requirement_id",
             "project_id"],
            ["plm.req_sources.requirement_source_id",
             "plm.req_sources.requirement_version_id",
             "plm.req_sources.requirement_id", "plm.req_sources.project_id"],
            name="fk_req_source_evidence__source", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_req_source_evidence__evidence",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_source_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_req_source_evidence__evidence", "req_source_evidence_refs",
                    ["evidence_id"], schema="plm")

    op.create_table(
        "req_assessment_evidence_refs",
        sa.Column("assessment_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("capability_assessment_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("evidence_role", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("capability_assessment_id", "evidence_id",
                            name="uq_req_assessment_evidence__assessment_evidence"),
        sa.UniqueConstraint("capability_assessment_id", "ordinal",
                            name="uq_req_assessment_evidence__assessment_ordinal"),
        sa.ForeignKeyConstraint(
            ["capability_assessment_id", "requirement_version_id", "requirement_id",
             "project_id"],
            ["plm.req_capability_assessments.capability_assessment_id",
             "plm.req_capability_assessments.requirement_version_id",
             "plm.req_capability_assessments.requirement_id",
             "plm.req_capability_assessments.project_id"],
            name="fk_req_assessment_evidence__assessment", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_req_assessment_evidence__evidence",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("evidence_role IN ('STANDARD','PROJECT')",
                           name="ck_req_assessment_evidence__role"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_assessment_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_req_assessment_evidence__evidence",
                    "req_assessment_evidence_refs", ["evidence_id"], schema="plm")

    op.create_table(
        "req_version_ai_task_refs",
        sa.Column("ai_task_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("task_scope", sa.Text(), nullable=False,
                  server_default=sa.text("'PROJECT'")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("requirement_version_id", "ai_task_id",
                            name="uq_req_version_ai_refs__version_task"),
        sa.UniqueConstraint("requirement_version_id", "ordinal",
                            name="uq_req_version_ai_refs__version_ordinal"),
        _version_fk("fk_req_version_ai_refs__version"),
        sa.ForeignKeyConstraint(
            ["ai_task_id", "task_scope", "project_id"],
            ["plm.ai_tasks.ai_task_id", "plm.ai_tasks.scope", "plm.ai_tasks.project_id"],
            name="fk_req_version_ai_refs__task", ondelete="NO ACTION"),
        sa.CheckConstraint("task_scope='PROJECT'", name="ck_req_version_ai_refs__scope"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_version_ai_refs__ordinal"),
        schema="plm",
    )
    op.create_index("ix_req_version_ai_refs__task", "req_version_ai_task_refs",
                    ["ai_task_id"], schema="plm")

    op.execute(_GUARDS)
    for table in _SUPPORT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW "
            "EXECUTE FUNCTION plm.guard_requirement_version_support()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_requirement_version_support_truncate()"
        )
    for table in _CLOSURE_TABLES:
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__completeness "
            f"AFTER INSERT OR UPDATE OR DELETE ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION plm.enforce_requirement_version_completeness()"
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RequirementVersion support downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _SUPPORT_TABLES):
        raise RuntimeError("RequirementVersion support history prevents downgrade")
    for table in _CLOSURE_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__completeness ON plm.{table}")
    for table in _SUPPORT_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    for table in reversed(_SUPPORT_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.enforce_requirement_version_completeness()")
    op.execute("DROP FUNCTION plm.guard_requirement_version_support()")
    op.execute("DROP FUNCTION plm.reject_requirement_version_support_truncate()")
