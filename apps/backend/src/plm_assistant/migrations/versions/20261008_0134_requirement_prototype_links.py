"""Add protected fixed-version RequirementPrototypeLink history.

Revision ID: 20261008_0134
Revises: 20261008_0133
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0134"
down_revision = "20261008_0133"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_prototype_link()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'RequirementPrototypeLink history is immutable';
  ELSIF TG_OP='INSERT' THEN
    IF NEW.link_state<>'ACTIVE' OR NEW.lock_version<>0
       OR NEW.superseded_by_ref IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementPrototypeLink initial state is invalid';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.requirement_prototype_link_id<>OLD.requirement_prototype_link_id
     OR NEW.project_id<>OLD.project_id
     OR NEW.requirement_id<>OLD.requirement_id
     OR NEW.requirement_version_id<>OLD.requirement_version_id
     OR NEW.prototype_id<>OLD.prototype_id
     OR NEW.prototype_version_id<>OLD.prototype_version_id
     OR NEW.purpose<>OLD.purpose
     OR NEW.coverage_schema_version<>OLD.coverage_schema_version
     OR NEW.coverage<>OLD.coverage
     OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
     OR OLD.link_state<>'ACTIVE' OR OLD.lock_version<>0
     OR NEW.lock_version<>1
     OR NEW.link_state NOT IN ('REVOKED','SUPERSEDED')
     OR (NEW.link_state='REVOKED' AND NEW.superseded_by_ref IS NOT NULL)
     OR (NEW.link_state='SUPERSEDED' AND NEW.superseded_by_ref IS NULL) THEN
    RAISE EXCEPTION 'RequirementPrototypeLink lifecycle mutation is invalid';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_requirement_prototype_replacement()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.link_state='SUPERSEDED' AND NOT EXISTS (
    SELECT 1 FROM plm.prt_requirement_links replacement
     WHERE replacement.requirement_prototype_link_id=NEW.superseded_by_ref
       AND replacement.project_id=NEW.project_id
       AND replacement.requirement_id=NEW.requirement_id
       AND replacement.prototype_id=NEW.prototype_id
       AND replacement.purpose=NEW.purpose
       AND replacement.link_state='ACTIVE'
       AND replacement.requirement_prototype_link_id<>
           NEW.requirement_prototype_link_id
       AND (replacement.requirement_version_id,
            replacement.prototype_version_id,
            replacement.coverage_schema_version,
            replacement.coverage) IS DISTINCT FROM
           (NEW.requirement_version_id,
            NEW.prototype_version_id,
            NEW.coverage_schema_version,
            NEW.coverage)
  ) THEN
    RAISE EXCEPTION 'RequirementPrototypeLink replacement is invalid';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_prototype_link_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementPrototypeLink history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    active = sa.text("link_state='ACTIVE'")
    op.create_table(
        "prt_requirement_links",
        sa.Column(
            "requirement_prototype_link_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column(
            "coverage_schema_version", sa.Integer(), nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.Column(
            "link_state", sa.Text(), nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_by", ident, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
            nullable=False, server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("superseded_by_ref", ident),
        sa.UniqueConstraint(
            "requirement_prototype_link_id", "project_id",
            name="uq_prt_requirement_links__id_project",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_prt_requirement_links__requirement_version",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_requirement_links__prototype_version",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_requirement_links__creator", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_ref", "project_id"],
            ["plm.prt_requirement_links.requirement_prototype_link_id",
             "plm.prt_requirement_links.project_id"],
            name="fk_prt_requirement_links__replacement", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "purpose IN ('ILLUSTRATES','VALIDATES','ACCEPTANCE_REFERENCE')",
            name="ck_prt_requirement_links__purpose",
        ),
        sa.CheckConstraint(
            "coverage_schema_version=1",
            name="ck_prt_requirement_links__coverage_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(coverage)='object' AND "
            "coverage - 'covered_acceptance_criterion_refs' - "
            "'uncovered_acceptance_criteria'='{}'::jsonb AND "
            "coverage ? 'covered_acceptance_criterion_refs' AND "
            "jsonb_typeof(coverage->'covered_acceptance_criterion_refs')='array' "
            "AND coverage ? 'uncovered_acceptance_criteria' AND "
            "jsonb_typeof(coverage->'uncovered_acceptance_criteria')='array' "
            "AND jsonb_array_length(coverage->"
            "'covered_acceptance_criterion_refs') BETWEEN 1 AND 500 AND "
            "jsonb_array_length(coverage->'uncovered_acceptance_criteria') "
            "BETWEEN 0 AND 499 AND pg_column_size(coverage)<=65536",
            name="ck_prt_requirement_links__coverage",
        ),
        sa.CheckConstraint(
            "(link_state='SUPERSEDED' AND superseded_by_ref IS NOT NULL "
            "AND superseded_by_ref<>requirement_prototype_link_id) OR "
            "(link_state IN ('ACTIVE','REVOKED') AND "
            "superseded_by_ref IS NULL)",
            name="ck_prt_requirement_links__state",
        ),
        sa.CheckConstraint(
            "(link_state='ACTIVE' AND lock_version=0) OR "
            "(link_state IN ('SUPERSEDED','REVOKED') AND lock_version=1)",
            name="ck_prt_requirement_links__lock",
        ),
        schema="plm",
    )
    op.create_index(
        "uq_prt_requirement_links__active_identity_purpose",
        "prt_requirement_links",
        ["project_id", "requirement_id", "prototype_id", "purpose"],
        unique=True, schema="plm", postgresql_where=active,
    )
    op.create_index(
        "ix_prt_requirement_links__requirement",
        "prt_requirement_links",
        ["project_id", "requirement_version_id", "purpose",
         "prototype_version_id"],
        schema="plm", postgresql_where=active,
    )
    op.create_index(
        "ix_prt_requirement_links__prototype",
        "prt_requirement_links",
        ["project_id", "prototype_version_id", "purpose",
         "requirement_version_id"],
        schema="plm", postgresql_where=active,
    )
    op.execute(sa.text(_GUARDS))
    op.execute(
        "CREATE TRIGGER trg_prt_requirement_links__guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.prt_requirement_links "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_prototype_link()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_requirement_links__replacement "
        "AFTER INSERT OR UPDATE ON plm.prt_requirement_links "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_requirement_prototype_replacement()"
    )
    op.execute(
        "CREATE TRIGGER trg_prt_requirement_links__no_truncate "
        "BEFORE TRUNCATE ON plm.prt_requirement_links FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_requirement_prototype_link_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "offline RequirementPrototypeLink downgrade is not allowed"
        )
    op.execute(
        "LOCK TABLE plm.prt_requirement_links IN ACCESS EXCLUSIVE MODE"
    )
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_requirement_links)"
    )).scalar_one():
        raise RuntimeError("RequirementPrototypeLink history prevents downgrade")
    op.execute(
        "DROP TRIGGER trg_prt_requirement_links__no_truncate "
        "ON plm.prt_requirement_links"
    )
    op.execute(
        "DROP TRIGGER trg_prt_requirement_links__replacement "
        "ON plm.prt_requirement_links"
    )
    op.execute(
        "DROP TRIGGER trg_prt_requirement_links__guard "
        "ON plm.prt_requirement_links"
    )
    op.drop_index(
        "ix_prt_requirement_links__prototype",
        table_name="prt_requirement_links", schema="plm",
    )
    op.drop_index(
        "ix_prt_requirement_links__requirement",
        table_name="prt_requirement_links", schema="plm",
    )
    op.drop_index(
        "uq_prt_requirement_links__active_identity_purpose",
        table_name="prt_requirement_links", schema="plm",
    )
    op.drop_table("prt_requirement_links", schema="plm")
    for function in (
        "guard_requirement_prototype_link",
        "assert_requirement_prototype_replacement",
        "reject_requirement_prototype_link_truncate",
    ):
        op.execute(f"DROP FUNCTION plm.{function}()")
