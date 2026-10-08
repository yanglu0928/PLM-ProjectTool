"""Close Prototype root mutation with immutable Version CREATE result.

Revision ID: 20261008_0135
Revises: 20261008_0134
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261008_0135"
down_revision = "20261008_0134"
branch_labels = None
depends_on = None


_RESULT_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'PrototypeVersion result is immutable'; END IF;
  IF NEW.prototype_lock_version IS NULL OR NOT EXISTS (
    SELECT 1 FROM plm.prt_prototype_versions v
    JOIN plm.prt_prototypes p ON p.prototype_id=v.prototype_id
      AND p.project_id=v.project_id
    WHERE v.prototype_version_id=NEW.prototype_version_id
      AND v.prototype_id=NEW.prototype_id AND v.project_id=NEW.project_id
      AND v.version_no=NEW.version_no AND v.version_state='DRAFT'
      AND v.content_fingerprint=NEW.content_fingerprint
      AND v.declared_artifact_count=NEW.declared_artifact_count
      AND v.declared_requirement_count=NEW.declared_requirement_count
      AND v.declared_interaction_count=NEW.declared_interaction_count
      AND p.prototype_state='ACTIVE'
      AND p.lock_version=NEW.prototype_lock_version
      AND p.updated_by=v.created_by
  ) THEN RAISE EXCEPTION 'PrototypeVersion result does not match root and version'; END IF;
  RETURN NEW;
END; $$;
"""

_ROOT_CLOSURE = r"""
CREATE OR REPLACE FUNCTION plm.assert_prototype_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM plm.prt_prototype_command_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.prototype_state=NEW.prototype_state
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
       AND r.lock_version=NEW.lock_version
  ) OR EXISTS (
    SELECT 1 FROM plm.prt_scope_decision_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND NEW.prototype_state='NOT_REQUIRED'
       AND NEW.current_approved_version_ref IS NULL AND r.lock_version=NEW.lock_version
  ) OR EXISTS (
    SELECT 1 FROM plm.prt_version_review_state_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.lock_version=NEW.lock_version AND r.actor_id=NEW.updated_by
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
  ) OR EXISTS (
    SELECT 1 FROM plm.prt_version_create_results r
    JOIN plm.prt_prototype_versions v
      ON v.prototype_version_id=r.prototype_version_id
      AND v.prototype_id=r.prototype_id AND v.project_id=r.project_id
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.prototype_lock_version=NEW.lock_version
       AND v.created_by=NEW.updated_by AND v.version_state='DRAFT'
       AND NEW.prototype_state='ACTIVE'
  ) THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Prototype mutation has no immutable result';
END; $$;
"""

_OLD_RESULT_GUARD = r"""
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
"""

_OLD_ROOT_CLOSURE = r"""
CREATE OR REPLACE FUNCTION plm.assert_prototype_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM plm.prt_prototype_command_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.prototype_state=NEW.prototype_state
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
       AND r.lock_version=NEW.lock_version
  ) OR EXISTS (
    SELECT 1 FROM plm.prt_scope_decision_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND NEW.prototype_state='NOT_REQUIRED'
       AND NEW.current_approved_version_ref IS NULL AND r.lock_version=NEW.lock_version
  ) OR EXISTS (
    SELECT 1 FROM plm.prt_version_review_state_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.lock_version=NEW.lock_version AND r.actor_id=NEW.updated_by
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
  ) THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Prototype mutation has no immutable result';
END; $$;
"""


def upgrade() -> None:
    op.add_column(
        "prt_version_create_results",
        sa.Column("prototype_lock_version", sa.BigInteger(), nullable=True),
        schema="plm",
    )
    op.create_check_constraint(
        "ck_prt_version_create_results__root_lock",
        "prt_version_create_results",
        "prototype_lock_version IS NULL OR prototype_lock_version>=1",
        schema="plm",
    )
    op.create_unique_constraint(
        "uq_prt_version_create_results__root_lock",
        "prt_version_create_results",
        ["prototype_id", "project_id", "prototype_lock_version"],
        schema="plm",
    )
    op.execute(sa.text(_RESULT_GUARD + _ROOT_CLOSURE))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype Version root closure downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.prt_prototypes, plm.prt_prototype_versions, "
        "plm.prt_version_create_results IN ACCESS EXCLUSIVE MODE"
    )
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_version_create_results "
        "WHERE prototype_lock_version IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Prototype Version CREATE history prevents downgrade")
    op.execute(sa.text(_OLD_RESULT_GUARD + _OLD_ROOT_CLOSURE))
    op.drop_constraint(
        "uq_prt_version_create_results__root_lock",
        "prt_version_create_results", schema="plm", type_="unique",
    )
    op.drop_constraint(
        "ck_prt_version_create_results__root_lock",
        "prt_version_create_results", schema="plm", type_="check",
    )
    op.drop_column("prt_version_create_results", "prototype_lock_version", schema="plm")
