"""Add PRT-01/PRT-02 identity, membership and NOT_REQUIRED scope schema.

Revision ID: 20261008_0122
Revises: 20261007_0121
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0122"
down_revision = "20261007_0121"
branch_labels = None
depends_on = None


_TABLES = (
    "prt_packages",
    "prt_prototypes",
    "prt_package_memberships",
    "prt_scope_decisions",
    "prt_scope_decision_requirement_refs",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_identity_scope_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME IN ('prt_scope_decisions',
                       'prt_scope_decision_requirement_refs') THEN
    RAISE EXCEPTION 'Prototype scope decision Owner is not installed';
  END IF;
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Prototype identity Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='prt_packages' THEN
    IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0
       OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'PrototypePackage initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='prt_prototypes' THEN
    IF NEW.prototype_state<>'ACTIVE'
       OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Prototype initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_identity_scope_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Prototype identity and scope history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "prt_packages",
        sa.Column(
            "prototype_package_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "package_state", sa.Text(), nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("created_by", ident, nullable=False),
        sa.Column(
            "created_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("updated_by", ident),
        sa.Column(
            "updated_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "prototype_package_id", "project_id",
            name="uq_prt_packages__id_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_packages__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_packages__creator", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["plm.auth_users.user_id"],
            name="fk_prt_packages__updater", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_packages__name",
        ),
        sa.CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_prt_packages__state",
        ),
        sa.CheckConstraint("lock_version>=0", name="ck_prt_packages__lock"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_packages__project_state", "prt_packages",
        ["project_id", "package_state", "prototype_package_id"], schema="plm",
    )
    op.create_table(
        "prt_prototypes",
        sa.Column(
            "prototype_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "prototype_state", sa.Text(), nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column(
            "created_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("updated_by", ident),
        sa.Column(
            "updated_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "prototype_id", "project_id", name="uq_prt_prototypes__id_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_prototypes__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_prototypes__creator", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["plm.auth_users.user_id"],
            name="fk_prt_prototypes__updater", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_prototypes__name",
        ),
        sa.CheckConstraint(
            "prototype_state IN ('ACTIVE','NOT_REQUIRED','ARCHIVED','RESTRICTED')",
            name="ck_prt_prototypes__state",
        ),
        sa.CheckConstraint("lock_version>=0", name="ck_prt_prototypes__lock"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_prototypes__project_state", "prt_prototypes",
        ["project_id", "prototype_state", "prototype_id"], schema="plm",
    )
    op.create_table(
        "prt_package_memberships",
        sa.Column(
            "prototype_package_membership_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("prototype_package_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("added_by", ident, nullable=False),
        sa.Column(
            "added_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.UniqueConstraint(
            "prototype_package_id", "prototype_id",
            name="uq_prt_package_memberships__package_prototype",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_package_id", "project_id"],
            ["plm.prt_packages.prototype_package_id", "plm.prt_packages.project_id"],
            name="fk_prt_package_memberships__package", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_package_memberships__prototype", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["added_by"], ["plm.auth_users.user_id"],
            name="fk_prt_package_memberships__adder", ondelete="NO ACTION",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_prt_package_memberships__prototype", "prt_package_memberships",
        ["prototype_id", "prototype_package_id"], schema="plm",
    )
    op.create_table(
        "prt_scope_decisions",
        sa.Column(
            "scope_decision_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("confirmed_by", ident, nullable=False),
        sa.Column("review_id", ident),
        sa.Column("review_round_id", ident),
        sa.Column(
            "decided_at", timestamp, nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("before_version", sa.BigInteger(), nullable=False),
        sa.Column("after_version", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint(
            "scope_decision_id", "prototype_id", "project_id",
            name="uq_prt_scope_decisions__id_prototype_project",
        ),
        sa.UniqueConstraint(
            "prototype_id", name="uq_prt_scope_decisions__prototype",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_scope_decisions__prototype", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"], ["plm.auth_users.user_id"],
            name="fk_prt_scope_decisions__confirmer", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["plm.rvw_reviews.review_id"],
            name="fk_prt_scope_decisions__review", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
            name="fk_prt_scope_decisions__round", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "decision_type='NOT_REQUIRED'", name="ck_prt_scope_decisions__type",
        ),
        sa.CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
            name="ck_prt_scope_decisions__reason",
        ),
        sa.CheckConstraint(
            "char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
            name="ck_prt_scope_decisions__impact",
        ),
        sa.CheckConstraint(
            "(review_id IS NULL AND review_round_id IS NULL) OR "
            "(review_id IS NOT NULL AND review_round_id IS NOT NULL)",
            name="ck_prt_scope_decisions__review_pair",
        ),
        sa.CheckConstraint(
            "before_version>=0 AND after_version=before_version+1",
            name="ck_prt_scope_decisions__version",
        ),
        schema="plm",
    )
    op.create_table(
        "prt_scope_decision_requirement_refs",
        sa.Column(
            "scope_decision_requirement_ref_id", ident, primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("scope_decision_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "scope_decision_id", "requirement_version_id",
            name="uq_prt_scope_req_refs__decision_version",
        ),
        sa.UniqueConstraint(
            "scope_decision_id", "ordinal",
            name="uq_prt_scope_req_refs__decision_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["scope_decision_id", "prototype_id", "project_id"],
            [
                "plm.prt_scope_decisions.scope_decision_id",
                "plm.prt_scope_decisions.prototype_id",
                "plm.prt_scope_decisions.project_id",
            ],
            name="fk_prt_scope_req_refs__decision", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            [
                "plm.req_requirement_versions.requirement_version_id",
                "plm.req_requirement_versions.requirement_id",
                "plm.req_requirement_versions.project_id",
            ],
            name="fk_prt_scope_req_refs__requirement_version", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("ordinal>0", name="ck_prt_scope_req_refs__ordinal"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_scope_req_refs__requirement_version",
        "prt_scope_decision_requirement_refs",
        ["requirement_version_id", "scope_decision_id"], schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_identity_scope_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_prototype_identity_scope_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype identity downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")
        ).scalar_one():
            raise RuntimeError("Prototype identity or scope history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_identity_scope_foundation()")
    op.execute("DROP FUNCTION plm.reject_prototype_identity_scope_truncate()")
