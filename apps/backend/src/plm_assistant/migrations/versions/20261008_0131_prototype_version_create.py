"""Open atomic PRT-03 DRAFT Version CREATE owner.

Revision ID: 20261008_0131
Revises: 20261008_0130
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0131"
down_revision = "20261008_0130"
branch_labels = None
depends_on = None

_OWNED = (
    "prt_prototype_versions", "prt_version_artifact_refs",
    "prt_version_requirement_refs", "prt_interaction_specs",
)

_OPEN_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_a integer; expected_r integer; latest_no integer; latest_id uuid;
        root_state text; found_count integer;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'PrototypeVersion history is immutable';
  END IF;
  IF TG_TABLE_NAME='prt_prototype_versions' THEN
    SELECT prototype_state INTO root_state FROM plm.prt_prototypes
     WHERE prototype_id=NEW.prototype_id AND project_id=NEW.project_id FOR UPDATE;
    IF NOT FOUND OR root_state<>'ACTIVE' OR NEW.version_state<>'DRAFT'
       OR NEW.review_ref IS NOT NULL OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'PrototypeVersion initial state is invalid';
    END IF;
    SELECT version_no,prototype_version_id INTO latest_no,latest_id
      FROM plm.prt_prototype_versions
     WHERE prototype_id=NEW.prototype_id AND project_id=NEW.project_id
     ORDER BY version_no DESC LIMIT 1;
    IF (latest_no IS NULL AND (NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
       OR (latest_no IS NOT NULL AND
           (NEW.version_no<>latest_no+1 OR NEW.supersedes_version_ref<>latest_id)) THEN
      RAISE EXCEPTION 'PrototypeVersion chain is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_version_artifact_refs' THEN
    SELECT declared_artifact_count INTO expected_a FROM plm.prt_prototype_versions
     WHERE prototype_version_id=NEW.prototype_version_id
       AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_a THEN
      RAISE EXCEPTION 'PrototypeVersion ArtifactRef is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_version_requirement_refs' THEN
    SELECT declared_requirement_count INTO expected_r FROM plm.prt_prototype_versions
     WHERE prototype_version_id=NEW.prototype_version_id
       AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_r THEN
      RAISE EXCEPTION 'PrototypeVersion RequirementRef is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_interaction_specs' THEN
    SELECT count(*) INTO found_count FROM plm.prt_prototype_versions
     WHERE prototype_version_id=NEW.prototype_version_id
       AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id
       AND declared_interaction_count=1;
    IF found_count<>1 THEN RAISE EXCEPTION 'PrototypeVersion InteractionSpec is invalid'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown PrototypeVersion table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_prototype_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE found_count integer;
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'PrototypeVersion result is immutable'; END IF;
  SELECT count(*) INTO found_count FROM plm.prt_prototype_versions v
   WHERE v.prototype_version_id=NEW.prototype_version_id
     AND v.prototype_id=NEW.prototype_id AND v.project_id=NEW.project_id
     AND v.version_no=NEW.version_no AND v.version_state='DRAFT'
     AND v.content_fingerprint=NEW.content_fingerprint
     AND v.declared_artifact_count=NEW.declared_artifact_count
     AND v.declared_requirement_count=NEW.declared_requirement_count
     AND v.declared_interaction_count=NEW.declared_interaction_count;
  IF found_count<>1 THEN RAISE EXCEPTION 'PrototypeVersion result does not match version'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_version_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ac integer; amin integer; amax integer; rc integer; rmin integer; rmax integer;
        ic integer; result_count integer;
BEGIN
  SELECT count(*),min(ordinal),max(ordinal) INTO ac,amin,amax
    FROM plm.prt_version_artifact_refs WHERE prototype_version_id=NEW.prototype_version_id;
  SELECT count(*),min(ordinal),max(ordinal) INTO rc,rmin,rmax
    FROM plm.prt_version_requirement_refs WHERE prototype_version_id=NEW.prototype_version_id;
  SELECT count(*) INTO ic FROM plm.prt_interaction_specs
   WHERE prototype_version_id=NEW.prototype_version_id;
  SELECT count(*) INTO result_count FROM plm.prt_version_create_results r
   WHERE r.prototype_version_id=NEW.prototype_version_id
     AND r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
     AND r.version_no=NEW.version_no AND r.content_fingerprint=NEW.content_fingerprint
     AND r.declared_artifact_count=NEW.declared_artifact_count
     AND r.declared_requirement_count=NEW.declared_requirement_count
     AND r.declared_interaction_count=1;
  IF ac<>NEW.declared_artifact_count OR amin<>1 OR amax<>ac
     OR rc<>NEW.declared_requirement_count OR rmin<>1 OR rmax<>rc
     OR ic<>1 OR result_count<>1 THEN
    RAISE EXCEPTION 'PrototypeVersion create set is incomplete';
  END IF;
  RETURN NULL;
END; $$;
"""

_CLOSED_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'PrototypeVersion Owner is not installed'; END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind.execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.prt_prototype_versions)"
        )).scalar_one():
            raise RuntimeError("pre-existing PrototypeVersion requires audited migration")
    op.create_table(
        "prt_version_create_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_artifact_count", sa.Integer(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("declared_interaction_count", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_version_create_results__version", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_prt_version_create_results__number"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_version_create_results__fingerprint"),
        sa.CheckConstraint(
            "declared_artifact_count BETWEEN 1 AND 100 AND "
            "declared_requirement_count BETWEEN 1 AND 200 AND "
            "declared_interaction_count=1",
            name="ck_prt_version_create_results__counts"),
        schema="plm",
    )
    for table in _OWNED:
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
    op.execute(_OPEN_GUARDS)
    for table in _OWNED:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_version_foundation()")
    op.execute(
        "CREATE TRIGGER trg_prt_version_create_results__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.prt_version_create_results FOR EACH ROW EXECUTE FUNCTION "
        "plm.guard_prototype_version_create_result()")
    op.execute(
        "CREATE TRIGGER trg_prt_version_create_results__no_truncate BEFORE TRUNCATE "
        "ON plm.prt_version_create_results FOR EACH STATEMENT EXECUTE FUNCTION "
        "plm.reject_prototype_version_truncate()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_versions__create_closure AFTER INSERT "
        "ON plm.prt_prototype_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_version_create_closure()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypeVersion create-owner downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_prototype_versions)"
    )).scalar_one():
        raise RuntimeError("PrototypeVersion create history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_versions__create_closure ON plm.prt_prototype_versions")
    op.execute("DROP TRIGGER trg_prt_version_create_results__owner ON plm.prt_version_create_results")
    op.execute("DROP TRIGGER trg_prt_version_create_results__no_truncate ON plm.prt_version_create_results")
    for table in _OWNED:
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
    op.execute("DROP FUNCTION plm.assert_prototype_version_create_closure()")
    op.execute("DROP FUNCTION plm.guard_prototype_version_create_result()")
    op.execute(_CLOSED_GUARD)
    for table in _OWNED:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_version_foundation()")
    op.drop_table("prt_version_create_results", schema="plm")
