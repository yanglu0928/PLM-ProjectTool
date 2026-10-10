"""Open atomic PRT-04 Template CREATE owner.

Revision ID: 20261008_0128
Revises: 20261008_0127
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261008_0128"
down_revision = "20261008_0127"
branch_labels = None
depends_on = None


_TABLES = (
    "prt_templates", "prt_template_versions",
    "prt_template_artifact_refs", "prt_template_command_results",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_template_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_scope text; parent_project uuid; parent_actor uuid;
        current_ref uuid; expected_count integer; actual_count integer;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'PrototypeTemplate history is immutable';
  END IF;
  IF TG_TABLE_NAME='prt_templates' THEN
    IF NEW.template_state<>'ACTIVE' OR NEW.current_template_version_ref IS NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'PrototypeTemplate initial state is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_template_versions' THEN
    SELECT scope,project_id,created_by,current_template_version_ref
      INTO parent_scope,parent_project,parent_actor,current_ref
      FROM plm.prt_templates WHERE prototype_template_id=NEW.prototype_template_id;
    IF NOT FOUND OR NEW.version_no<>1 OR NEW.version_state<>'PUBLISHED'
       OR NEW.supersedes_version_id IS NOT NULL
       OR NEW.scope<>parent_scope
       OR NEW.project_id IS DISTINCT FROM parent_project
       OR NEW.created_by<>parent_actor
       OR NEW.prototype_template_version_id<>current_ref
       OR NEW.applicable_terminals IS DISTINCT FROM ARRAY(
         SELECT DISTINCT item FROM unnest(NEW.applicable_terminals) item ORDER BY item)
       OR EXISTS (SELECT 1 FROM unnest(NEW.applicable_terminals) item
                  WHERE item !~ '^[A-Z][A-Z0-9_]{0,63}$') THEN
      RAISE EXCEPTION 'PrototypeTemplate first version is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_template_artifact_refs' THEN
    SELECT scope,project_id,declared_artifact_count
      INTO parent_scope,parent_project,expected_count
      FROM plm.prt_template_versions
     WHERE prototype_template_version_id=NEW.prototype_template_version_id
       AND prototype_template_id=NEW.prototype_template_id;
    IF NOT FOUND OR NEW.scope<>parent_scope
       OR NEW.project_id IS DISTINCT FROM parent_project
       OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'PrototypeTemplate ArtifactRef is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_template_command_results' THEN
    IF NEW.operation<>'CREATE' OR NEW.version_no<>1 OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'PrototypeTemplate create result is invalid';
    END IF;
    SELECT count(*) INTO actual_count
      FROM plm.prt_templates t JOIN plm.prt_template_versions v
        ON v.prototype_template_id=t.prototype_template_id
       AND v.prototype_template_version_id=t.current_template_version_ref
     WHERE t.prototype_template_id=NEW.prototype_template_id
       AND v.prototype_template_version_id=NEW.prototype_template_version_id
       AND t.scope=NEW.scope AND t.project_id IS NOT DISTINCT FROM NEW.project_id
       AND v.scope=NEW.scope AND v.project_id IS NOT DISTINCT FROM NEW.project_id
       AND t.name=NEW.name AND v.version_no=NEW.version_no
       AND v.content_fingerprint=NEW.content_fingerprint
       AND v.declared_artifact_count=NEW.declared_artifact_count;
    IF actual_count<>1 THEN
      RAISE EXCEPTION 'PrototypeTemplate create result does not match root/version';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown PrototypeTemplate table';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_template_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_count integer; artifact_count integer; result_count integer;
BEGIN
  SELECT count(*),COALESCE(max(v.declared_artifact_count),-1)
    INTO version_count,artifact_count
    FROM plm.prt_template_versions v
   WHERE v.prototype_template_version_id=NEW.current_template_version_ref
     AND v.prototype_template_id=NEW.prototype_template_id
     AND v.scope=NEW.scope AND v.project_id IS NOT DISTINCT FROM NEW.project_id
     AND v.version_no=1 AND v.version_state='PUBLISHED'
     AND v.supersedes_version_id IS NULL AND v.created_by=NEW.created_by;
  IF version_count<>1 THEN
    RAISE EXCEPTION 'PrototypeTemplate has no complete first version';
  END IF;
  IF artifact_count<>(SELECT count(*) FROM plm.prt_template_artifact_refs a
      WHERE a.prototype_template_version_id=NEW.current_template_version_ref
        AND a.prototype_template_id=NEW.prototype_template_id) THEN
    RAISE EXCEPTION 'PrototypeTemplate ArtifactRef set is incomplete';
  END IF;
  SELECT count(*) INTO result_count FROM plm.prt_template_command_results r
   WHERE r.prototype_template_id=NEW.prototype_template_id
     AND r.prototype_template_version_id=NEW.current_template_version_ref
     AND r.scope=NEW.scope AND r.project_id IS NOT DISTINCT FROM NEW.project_id
     AND r.operation='CREATE' AND r.name=NEW.name AND r.version_no=1
     AND r.declared_artifact_count=artifact_count AND r.lock_version=0;
  IF result_count<>1 THEN
    RAISE EXCEPTION 'PrototypeTemplate has no immutable create result';
  END IF;
  RETURN NULL;
END; $$;
"""

_CLOSED_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_template_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PrototypeTemplate Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        if any(bind.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
        )).scalar_one() for table in _TABLES):
            raise RuntimeError("pre-existing PrototypeTemplate requires audited migration")
    op.add_column(
        "prt_template_versions",
        sa.Column("declared_artifact_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")), schema="plm",
    )
    op.create_check_constraint(
        "ck_prt_template_versions__artifact_count", "prt_template_versions",
        "declared_artifact_count BETWEEN 0 AND 100", schema="plm",
    )
    op.add_column(
        "prt_template_command_results",
        sa.Column("declared_artifact_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")), schema="plm",
    )
    op.create_check_constraint(
        "ck_prt_template_command_results__artifact_count",
        "prt_template_command_results",
        "declared_artifact_count BETWEEN 0 AND 100", schema="plm",
    )
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_template_foundation()"
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_templates__create_closure AFTER INSERT "
        "ON plm.prt_templates DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_template_create_closure()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypeTemplate create-owner downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES):
        raise RuntimeError("PrototypeTemplate create history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_templates__create_closure ON plm.prt_templates")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
    op.execute("DROP FUNCTION plm.assert_prototype_template_create_closure()")
    op.execute(_CLOSED_GUARDS)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_template_foundation()"
        )
    op.drop_constraint(
        "ck_prt_template_command_results__artifact_count",
        "prt_template_command_results", schema="plm", type_="check",
    )
    op.drop_column(
        "prt_template_command_results", "declared_artifact_count", schema="plm",
    )
    op.drop_constraint(
        "ck_prt_template_versions__artifact_count", "prt_template_versions",
        schema="plm", type_="check",
    )
    op.drop_column(
        "prt_template_versions", "declared_artifact_count", schema="plm",
    )
