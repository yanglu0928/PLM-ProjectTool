"""Add protected fixed-version RequirementRelation history.

Revision ID: 20261007_0121
Revises: 20261007_0120
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0121"
down_revision = "20261007_0120"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_relation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE replacement plm.req_relations%ROWTYPE;
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'RequirementRelation history is immutable';
  ELSIF TG_OP='INSERT' THEN
    IF NEW.relation_state<>'ACTIVE' OR NEW.lock_version<>0
       OR NEW.superseded_by_ref IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementRelation initial state is invalid'; END IF;
    IF NEW.relation_type IN ('DUPLICATES','CONFLICTS_WITH')
       AND NOT (ROW(NEW.source_requirement_id,NEW.source_requirement_version_id)
                < ROW(NEW.target_requirement_id,NEW.target_requirement_version_id)) THEN
      RAISE EXCEPTION 'RequirementRelation symmetric endpoints are not canonical'; END IF;
    RETURN NEW;
  END IF;
  IF NEW.requirement_relation_id<>OLD.requirement_relation_id
     OR NEW.project_id<>OLD.project_id
     OR NEW.source_requirement_id<>OLD.source_requirement_id
     OR NEW.source_requirement_version_id<>OLD.source_requirement_version_id
     OR NEW.target_requirement_id<>OLD.target_requirement_id
     OR NEW.target_requirement_version_id<>OLD.target_requirement_version_id
     OR NEW.relation_type<>OLD.relation_type
     OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
     OR OLD.relation_state<>'ACTIVE' OR OLD.lock_version<>0
     OR NEW.lock_version<>1
     OR NEW.relation_state NOT IN ('REVOKED','SUPERSEDED')
     OR (NEW.relation_state='REVOKED' AND NEW.superseded_by_ref IS NOT NULL)
     OR (NEW.relation_state='SUPERSEDED' AND NEW.superseded_by_ref IS NULL) THEN
    RAISE EXCEPTION 'RequirementRelation lifecycle mutation is invalid'; END IF;
  IF NEW.relation_state='SUPERSEDED' THEN
    SELECT * INTO replacement FROM plm.req_relations
     WHERE requirement_relation_id=NEW.superseded_by_ref
       AND project_id=NEW.project_id FOR SHARE;
    IF replacement.requirement_relation_id IS NULL
       OR replacement.relation_state<>'ACTIVE'
       OR replacement.requirement_relation_id=NEW.requirement_relation_id THEN
      RAISE EXCEPTION 'RequirementRelation replacement is invalid'; END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_relation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementRelation history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    op.create_table(
        "req_relations",
        sa.Column(
            "requirement_relation_id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_requirement_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "source_requirement_version_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "target_requirement_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "target_requirement_version_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column(
            "relation_state", sa.Text(), nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
            nullable=False, server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("superseded_by_ref", postgresql.UUID(as_uuid=True)),
        sa.UniqueConstraint(
            "requirement_relation_id", "project_id",
            name="uq_req_relations__id_project",
        ),
        sa.ForeignKeyConstraint(
            ["source_requirement_version_id", "source_requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_relations__source_version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["target_requirement_version_id", "target_requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_relations__target_version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_req_relations__creator", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_ref", "project_id"],
            ["plm.req_relations.requirement_relation_id",
             "plm.req_relations.project_id"],
            name="fk_req_relations__replacement", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "relation_type IN ('DEPENDS_ON','PARENT_OF','RELATED_TO',"
            "'DUPLICATES','CONFLICTS_WITH')",
            name="ck_req_relations__type",
        ),
        sa.CheckConstraint(
            "source_requirement_version_id<>target_requirement_version_id",
            name="ck_req_relations__not_self",
        ),
        sa.CheckConstraint(
            "relation_type NOT IN ('DUPLICATES','CONFLICTS_WITH') OR "
            "ROW(source_requirement_id,source_requirement_version_id)<"
            "ROW(target_requirement_id,target_requirement_version_id)",
            name="ck_req_relations__symmetric_order",
        ),
        sa.CheckConstraint(
            "(relation_state='SUPERSEDED' AND superseded_by_ref IS NOT NULL "
            "AND superseded_by_ref<>requirement_relation_id) OR "
            "(relation_state IN ('ACTIVE','REVOKED') AND "
            "superseded_by_ref IS NULL)",
            name="ck_req_relations__state",
        ),
        sa.CheckConstraint(
            "(relation_state='ACTIVE' AND lock_version=0) OR "
            "(relation_state IN ('SUPERSEDED','REVOKED') AND lock_version=1)",
            name="ck_req_relations__lock",
        ),
        schema="plm",
    )
    active = sa.text("relation_state='ACTIVE'")
    op.create_index(
        "uq_req_relations__active_edge", "req_relations",
        ["project_id", "source_requirement_version_id", "relation_type",
         "target_requirement_version_id"], unique=True, schema="plm",
        postgresql_where=active,
    )
    op.create_index(
        "ix_req_relations__out", "req_relations",
        ["project_id", "source_requirement_version_id", "relation_type",
         "target_requirement_version_id"], schema="plm",
        postgresql_where=active,
    )
    op.create_index(
        "ix_req_relations__in", "req_relations",
        ["project_id", "target_requirement_version_id", "relation_type",
         "source_requirement_version_id"], schema="plm",
        postgresql_where=active,
    )
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_req_relations__guard BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.req_relations FOR EACH ROW EXECUTE FUNCTION "
        "plm.guard_requirement_relation()"
    )
    op.execute(
        "CREATE TRIGGER trg_req_relations__no_truncate BEFORE TRUNCATE "
        "ON plm.req_relations FOR EACH STATEMENT EXECUTE FUNCTION "
        "plm.reject_requirement_relation_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RequirementRelation downgrade is not allowed")
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_relations)"
    )).scalar_one():
        raise RuntimeError("RequirementRelation history prevents downgrade")
    op.execute("DROP TRIGGER trg_req_relations__guard ON plm.req_relations")
    op.execute("DROP TRIGGER trg_req_relations__no_truncate ON plm.req_relations")
    op.execute("DROP FUNCTION plm.guard_requirement_relation()")
    op.execute("DROP FUNCTION plm.reject_requirement_relation_truncate()")
    op.drop_index(
        "ix_req_relations__in", table_name="req_relations", schema="plm"
    )
    op.drop_index(
        "ix_req_relations__out", table_name="req_relations", schema="plm"
    )
    op.drop_index(
        "uq_req_relations__active_edge", table_name="req_relations", schema="plm"
    )
    op.drop_table("req_relations", schema="plm")
