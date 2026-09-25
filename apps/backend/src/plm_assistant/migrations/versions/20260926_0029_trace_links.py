"""TRC-01 protected, fixed-version TraceLink history.

Revision ID: 20260926_0029
Revises: 20260926_0028
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260926_0029"
down_revision = "20260926_0028"
branch_labels = None
depends_on = None

_ID = postgresql.UUID(as_uuid=True)
_TIME = postgresql.TIMESTAMP(timezone=True, precision=6)
_PAIR = (
    "({role}_owner_module='document' AND {role}_object_type='DOC-02') OR "
    "({role}_owner_module='capability' AND {role}_object_type='CAP-02') OR "
    "({role}_owner_module='handover' AND {role}_object_type='HND-02') OR "
    "({role}_owner_module='survey' AND {role}_object_type IN ('SRV-02','SRV-05')) OR "
    "({role}_owner_module='requirement' AND {role}_object_type='REQ-03') OR "
    "({role}_owner_module='prototype' AND {role}_object_type IN ('PRT-03','PRT-04')) OR "
    "({role}_owner_module='solution' AND {role}_object_type IN ('SOL-01','SOL-03','SOL-05','SOL-06')) OR "
    "({role}_owner_module='plan' AND {role}_object_type IN ('PLN-02','PLN-03')) OR "
    "({role}_owner_module='output' AND {role}_object_type='OUT-02')"
)
_EDGE_SCOPE = (
    "(scope='GLOBAL' AND project_id IS NULL AND source_project_id IS NULL "
    "AND target_project_id IS NULL AND relation_type<>'REFERENCES_CAPABILITY') OR "
    "(scope='PROJECT' AND project_id IS NOT NULL AND target_project_id IS NOT NULL "
    "AND target_project_id=project_id AND "
    "((source_project_id IS NOT NULL AND source_project_id=project_id "
    "AND relation_type<>'REFERENCES_CAPABILITY') OR "
    "(source_project_id IS NULL AND relation_type IN ('DERIVED_FROM','REFERENCES_CAPABILITY') "
    "AND ((source_owner_module='capability' AND source_object_type='CAP-02') "
    "OR (source_owner_module='document' AND source_object_type='DOC-02' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='prototype' AND source_object_type='PRT-04' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='solution' AND source_object_type='SOL-01' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='plan' AND source_object_type='PLN-03' "
    "AND relation_type='DERIVED_FROM')))))"
)


def upgrade() -> None:
    op.create_table(
        "trc_links",
        sa.Column("trace_link_id", _ID, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", _ID),
        sa.Column("source_owner_module", sa.Text(), nullable=False),
        sa.Column("source_object_type", sa.Text(), nullable=False),
        sa.Column("source_object_id", _ID, nullable=False),
        sa.Column("source_version_id", _ID, nullable=False),
        sa.Column("source_project_id", _ID),
        sa.Column("target_owner_module", sa.Text(), nullable=False),
        sa.Column("target_object_type", sa.Text(), nullable=False),
        sa.Column("target_object_id", _ID, nullable=False),
        sa.Column("target_version_id", _ID, nullable=False),
        sa.Column("target_project_id", _ID),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("link_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("created_by", _ID, nullable=False),
        sa.Column("created_at", _TIME, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("trace_id", _ID, nullable=False),
        sa.Column("superseded_by_ref", _ID),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_trc_links__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_trc_links__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["superseded_by_ref"], ["plm.trc_links.trace_link_id"],
                                name="fk_trc_links__replacement", ondelete="NO ACTION"),
        sa.CheckConstraint(f"({_PAIR.format(role='source')})",
                           name="ck_trc_links__source_type"),
        sa.CheckConstraint(f"({_PAIR.format(role='target')})",
                           name="ck_trc_links__target_type"),
        sa.CheckConstraint(_EDGE_SCOPE, name="ck_trc_links__scope"),
        sa.CheckConstraint("NOT (source_owner_module=target_owner_module AND "
                           "source_object_type=target_object_type AND "
                           "source_object_id=target_object_id AND "
                           "source_version_id=target_version_id)",
                           name="ck_trc_links__not_self"),
        sa.CheckConstraint("source_object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                           "AND source_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                           "AND target_object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                           "AND target_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                           "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid",
                           name="ck_trc_links__identities"),
        sa.CheckConstraint("relation_type IN ('DERIVED_FROM','REFINES','IMPLEMENTS',"
                           "'VALIDATES','GENERATED_FROM','REFERENCES_CAPABILITY','SUPERSEDES')",
                           name="ck_trc_links__relation"),
        sa.CheckConstraint("(link_state='SUPERSEDED' AND superseded_by_ref IS NOT NULL "
                           "AND superseded_by_ref<>trace_link_id) OR "
                           "(link_state IN ('ACTIVE','REVOKED') AND superseded_by_ref IS NULL)",
                           name="ck_trc_links__state"),
        schema="plm",
    )
    op.create_index("uq_trc_links__active_edge", "trc_links",
                    ["source_owner_module", "source_object_type", "source_object_id",
                     "source_version_id", "target_owner_module", "target_object_type",
                     "target_object_id", "target_version_id", "relation_type"],
                    unique=True, postgresql_where=sa.text("link_state='ACTIVE'"), schema="plm")
    op.create_index("ix_trc_links__source_active", "trc_links",
                    ["source_owner_module", "source_object_type", "source_version_id",
                     "source_project_id", "relation_type", "target_version_id"],
                    postgresql_where=sa.text("link_state='ACTIVE'"), schema="plm")
    op.create_index("ix_trc_links__target_active", "trc_links",
                    ["target_owner_module", "target_object_type", "target_version_id",
                     "target_project_id", "relation_type", "source_version_id"],
                    postgresql_where=sa.text("link_state='ACTIVE'"), schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_trace_link()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            replacement_scope text;
            replacement_project uuid;
            replacement_state text;
            replacement_created timestamptz;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'TraceLink history is retained';
            END IF;
            IF TG_OP='INSERT' THEN
                IF NEW.link_state<>'ACTIVE' OR NEW.superseded_by_ref IS NOT NULL THEN
                    RAISE EXCEPTION 'TraceLink initial state invalid';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(NEW.trace_link_id,NEW.scope,NEW.project_id,
                   NEW.source_owner_module,NEW.source_object_type,
                   NEW.source_object_id,NEW.source_version_id,NEW.source_project_id,
                   NEW.target_owner_module,NEW.target_object_type,
                   NEW.target_object_id,NEW.target_version_id,NEW.target_project_id,
                   NEW.relation_type,NEW.created_by,NEW.created_at,NEW.trace_id)
               IS DISTINCT FROM
               ROW(OLD.trace_link_id,OLD.scope,OLD.project_id,
                   OLD.source_owner_module,OLD.source_object_type,
                   OLD.source_object_id,OLD.source_version_id,OLD.source_project_id,
                   OLD.target_owner_module,OLD.target_object_type,
                   OLD.target_object_id,OLD.target_version_id,OLD.target_project_id,
                   OLD.relation_type,OLD.created_by,OLD.created_at,OLD.trace_id)
               OR OLD.link_state<>'ACTIVE'
               OR NEW.link_state NOT IN ('SUPERSEDED','REVOKED') THEN
                RAISE EXCEPTION 'TraceLink history transition invalid';
            END IF;
            IF NEW.link_state='SUPERSEDED' THEN
                SELECT scope,project_id,link_state,created_at
                  INTO replacement_scope,replacement_project,replacement_state,
                       replacement_created
                  FROM plm.trc_links
                 WHERE trace_link_id=NEW.superseded_by_ref FOR SHARE;
                IF NOT FOUND OR replacement_scope IS DISTINCT FROM OLD.scope
                   OR replacement_project IS DISTINCT FROM OLD.project_id
                   OR replacement_state<>'ACTIVE'
                   OR replacement_created < OLD.created_at THEN
                    RAISE EXCEPTION 'TraceLink replacement invalid';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_trc_link_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.trc_links
        FOR EACH ROW EXECUTE FUNCTION plm.guard_trace_link()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for TraceLink")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.trc_links)")):
        raise RuntimeError("TraceLink history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_trc_link_guard ON plm.trc_links")
    op.execute("DROP FUNCTION plm.guard_trace_link()")
    op.drop_index("ix_trc_links__target_active", table_name="trc_links", schema="plm")
    op.drop_index("ix_trc_links__source_active", table_name="trc_links", schema="plm")
    op.drop_index("uq_trc_links__active_edge", table_name="trc_links", schema="plm")
    op.drop_table("trc_links", schema="plm")
