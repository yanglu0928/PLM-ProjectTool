"""Open atomic PRT-04 Template REVISE owner.

Revision ID: 20261008_0129
Revises: 20261008_0128
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261008_0129"
down_revision = "20261008_0128"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_template_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_scope text; parent_project uuid; parent_actor uuid;
        current_ref uuid; current_no integer; expected_count integer;
        actual_count integer;
BEGIN
  IF TG_TABLE_NAME='prt_templates' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.template_state<>'ACTIVE' OR NEW.current_template_version_ref IS NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'PrototypeTemplate initial state is invalid';
      END IF;
      RETURN NEW;
    ELSIF TG_OP='UPDATE' THEN
      IF NEW.prototype_template_id<>OLD.prototype_template_id
         OR NEW.scope<>OLD.scope OR NEW.project_id IS DISTINCT FROM OLD.project_id
         OR NEW.name<>OLD.name OR OLD.template_state<>'ACTIVE'
         OR NEW.template_state<>'ACTIVE' OR NEW.created_by<>OLD.created_by
         OR NEW.created_at<>OLD.created_at
         OR NEW.current_template_version_ref=OLD.current_template_version_ref
         OR NEW.updated_by IS NULL OR NEW.lock_version<>OLD.lock_version+1
         OR NEW.updated_at<OLD.updated_at THEN
        RAISE EXCEPTION 'PrototypeTemplate revision update is invalid';
      END IF;
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'PrototypeTemplate history is immutable';
  ELSIF TG_TABLE_NAME='prt_template_versions' THEN
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'PrototypeTemplate history is immutable';
    END IF;
    SELECT t.scope,t.project_id,t.created_by,t.current_template_version_ref,
           v.version_no
      INTO parent_scope,parent_project,parent_actor,current_ref,current_no
      FROM plm.prt_templates t LEFT JOIN plm.prt_template_versions v
        ON v.prototype_template_version_id=t.current_template_version_ref
       AND v.prototype_template_id=t.prototype_template_id
     WHERE t.prototype_template_id=NEW.prototype_template_id;
    IF NOT FOUND OR NEW.version_state<>'PUBLISHED'
       OR NEW.scope<>parent_scope OR NEW.project_id IS DISTINCT FROM parent_project
       OR NEW.applicable_terminals IS DISTINCT FROM ARRAY(
         SELECT DISTINCT item FROM unnest(NEW.applicable_terminals) item ORDER BY item)
       OR EXISTS (SELECT 1 FROM unnest(NEW.applicable_terminals) item
                  WHERE item !~ '^[A-Z][A-Z0-9_]{0,63}$') THEN
      RAISE EXCEPTION 'PrototypeTemplate version is invalid';
    END IF;
    IF NEW.prototype_template_version_id=current_ref THEN
      IF NEW.version_no<>1 OR NEW.supersedes_version_id IS NOT NULL
         OR NEW.created_by<>parent_actor THEN
        RAISE EXCEPTION 'PrototypeTemplate first version is invalid';
      END IF;
    ELSIF current_no IS NULL OR NEW.version_no<>current_no+1
       OR NEW.supersedes_version_id<>current_ref THEN
      RAISE EXCEPTION 'PrototypeTemplate revision version is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_template_artifact_refs' THEN
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'PrototypeTemplate history is immutable';
    END IF;
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
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'PrototypeTemplate history is immutable';
    END IF;
    IF NEW.operation='CREATE' THEN
      IF NEW.version_no<>1 OR NEW.lock_version<>0 THEN
        RAISE EXCEPTION 'PrototypeTemplate create result is invalid';
      END IF;
    ELSIF NEW.operation='REVISE' THEN
      IF NEW.version_no<2 OR NEW.lock_version<>NEW.version_no-1 THEN
        RAISE EXCEPTION 'PrototypeTemplate revise result is invalid';
      END IF;
    ELSE
      RAISE EXCEPTION 'PrototypeTemplate operation is invalid';
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
       AND v.declared_artifact_count=NEW.declared_artifact_count
       AND t.lock_version=NEW.lock_version
       AND (NEW.operation='CREATE' OR (
         v.supersedes_version_id IS NOT NULL AND t.updated_by=v.created_by));
    IF actual_count<>1 THEN
      RAISE EXCEPTION 'PrototypeTemplate result does not match root/version';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown PrototypeTemplate table';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_template_revise_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_no integer; version_count integer; artifact_count integer;
        result_count integer;
BEGIN
  SELECT version_no INTO old_no FROM plm.prt_template_versions
   WHERE prototype_template_version_id=OLD.current_template_version_ref
     AND prototype_template_id=OLD.prototype_template_id;
  IF old_no IS NULL OR old_no<>OLD.lock_version+1 THEN
    RAISE EXCEPTION 'PrototypeTemplate prior version is inconsistent';
  END IF;
  SELECT count(*),COALESCE(max(v.declared_artifact_count),-1)
    INTO version_count,artifact_count FROM plm.prt_template_versions v
   WHERE v.prototype_template_version_id=NEW.current_template_version_ref
     AND v.prototype_template_id=NEW.prototype_template_id
     AND v.scope=NEW.scope AND v.project_id IS NOT DISTINCT FROM NEW.project_id
     AND v.version_no=old_no+1 AND v.version_state='PUBLISHED'
     AND v.supersedes_version_id=OLD.current_template_version_ref
     AND v.created_by=NEW.updated_by;
  IF version_count<>1 OR NEW.lock_version<>old_no THEN
    RAISE EXCEPTION 'PrototypeTemplate has no complete revision version';
  END IF;
  IF artifact_count<>(SELECT count(*) FROM plm.prt_template_artifact_refs a
      WHERE a.prototype_template_version_id=NEW.current_template_version_ref
        AND a.prototype_template_id=NEW.prototype_template_id) THEN
    RAISE EXCEPTION 'PrototypeTemplate revision ArtifactRef set is incomplete';
  END IF;
  SELECT count(*) INTO result_count FROM plm.prt_template_command_results r
   WHERE r.prototype_template_id=NEW.prototype_template_id
     AND r.prototype_template_version_id=NEW.current_template_version_ref
     AND r.scope=NEW.scope AND r.project_id IS NOT DISTINCT FROM NEW.project_id
     AND r.operation='REVISE' AND r.name=NEW.name AND r.version_no=old_no+1
     AND r.declared_artifact_count=artifact_count
     AND r.lock_version=NEW.lock_version;
  IF result_count<>1 THEN
    RAISE EXCEPTION 'PrototypeTemplate has no immutable revise result';
  END IF;
  RETURN NULL;
END; $$;
"""


_CREATE_ONLY_GUARD = r"""
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
"""


def upgrade() -> None:
    op.execute(_GUARDS)
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_templates__revise_closure AFTER UPDATE "
        "ON plm.prt_templates DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_template_revise_closure()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypeTemplate revise-owner downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_template_command_results "
        "WHERE operation='REVISE')"
    )).scalar_one():
        raise RuntimeError("PrototypeTemplate revise history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_templates__revise_closure ON plm.prt_templates")
    op.execute("DROP FUNCTION plm.assert_prototype_template_revise_closure()")
    op.execute(_CREATE_ONLY_GUARD)
