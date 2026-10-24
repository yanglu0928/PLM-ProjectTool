"""Open complete immutable RequirementVersion draft creation.

Revision ID: 20261007_0119
Revises: 20261007_0118
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0119"
down_revision = "20261007_0118"
branch_labels = None
depends_on = None


_OWNER_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_primary()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest record;
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'RequirementVersion is immutable'; END IF;
  IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
     OR NEW.review_round_ref IS NOT NULL THEN
    RAISE EXCEPTION 'RequirementVersion initial state is invalid';
  END IF;
  SELECT requirement_version_id,version_no INTO latest
    FROM plm.req_requirement_versions
   WHERE requirement_id=NEW.requirement_id AND project_id=NEW.project_id
   ORDER BY version_no DESC LIMIT 1;
  IF NOT FOUND THEN
    IF NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementVersion initial base is invalid'; END IF;
  ELSIF NEW.version_no<>latest.version_no+1
     OR NEW.supersedes_version_ref<>latest.requirement_version_id THEN
    RAISE EXCEPTION 'RequirementVersion base does not match current highest version';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_version_owned()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'RequirementVersion content is immutable'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_version_support()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'RequirementVersion support is immutable'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'RequirementVersion create result is immutable'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM plm.req_requirements r
     WHERE r.requirement_id=NEW.requirement_id AND r.project_id=NEW.project_id
       AND r.requirement_state='ACTIVE' AND r.lock_version=NEW.lock_version
       AND r.updated_by=NEW.actor_id
  ) OR NOT EXISTS (
    SELECT 1 FROM plm.req_requirement_versions v
     WHERE v.requirement_version_id=NEW.requirement_version_id
       AND v.requirement_id=NEW.requirement_id AND v.project_id=NEW.project_id
       AND v.version_state='DRAFT' AND v.created_by=NEW.actor_id
       AND v.content_fingerprint=NEW.content_fingerprint
       AND v.review_ref IS NULL AND v.review_round_ref IS NULL
  ) THEN RAISE EXCEPTION 'RequirementVersion create result does not match root/version'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_version_create_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementVersion create result history cannot be truncated';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_version_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.req_requirement_version_create_results x
     WHERE x.requirement_version_id=NEW.requirement_version_id
       AND x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.actor_id=NEW.created_by AND x.content_fingerprint=NEW.content_fingerprint
  ) THEN RAISE EXCEPTION 'RequirementVersion has no immutable create result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM plm.req_requirement_command_results x
     WHERE x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.requirement_code=NEW.requirement_code
       AND x.requirement_state=NEW.requirement_state AND x.lock_version=NEW.lock_version
  ) OR EXISTS (
    SELECT 1 FROM plm.req_requirement_version_create_results x
     WHERE x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.lock_version=NEW.lock_version AND x.actor_id=NEW.updated_by
  ) THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Requirement mutation has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='req_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'RequirementPackage initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'RequirementPackage history is immutable'; END IF;
    IF NEW.requirement_package_id<>OLD.requirement_package_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR OLD.package_state='ARCHIVED'
       OR (OLD.package_state='ACTIVE' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED'))
       OR (OLD.package_state='RESTRICTED' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED')) THEN
      RAISE EXCEPTION 'RequirementPackage mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Requirement initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'Requirement identity history is immutable'; END IF;
    IF NEW.requirement_id<>OLD.requirement_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.requirement_code_normalized<>upper(NEW.requirement_code)
       OR NOT (
         (OLD.requirement_state='ACTIVE' AND NEW.requirement_state='ACTIVE')
         OR (OLD.requirement_state='ACTIVE' AND NEW.requirement_state IN ('DEFERRED','REJECTED')
             AND NEW.requirement_code=OLD.requirement_code)
         OR (OLD.requirement_state<>'ARCHIVED' AND NEW.requirement_state='ARCHIVED'
             AND NEW.requirement_code=OLD.requirement_code)
       ) THEN RAISE EXCEPTION 'Requirement identity mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Requirement identity table';
END; $$;
"""

_CLOSED_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_primary()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementVersion Owner is not installed';
END; $$;
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_owned()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementVersion owned collection Owner is not installed';
END; $$;
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_support()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'RequirementVersion support Owner is not installed';
END; $$;
CREATE OR REPLACE FUNCTION plm.enforce_requirement_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.req_requirement_command_results x
     WHERE x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.requirement_code=NEW.requirement_code
       AND x.requirement_state=NEW.requirement_state AND x.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Requirement mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='req_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'RequirementPackage initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'RequirementPackage history is immutable'; END IF;
    IF NEW.requirement_package_id<>OLD.requirement_package_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR OLD.package_state='ARCHIVED'
       OR (OLD.package_state='ACTIVE' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED'))
       OR (OLD.package_state='RESTRICTED' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED')) THEN
      RAISE EXCEPTION 'RequirementPackage mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Requirement initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'Requirement identity history is immutable'; END IF;
    IF NEW.requirement_id<>OLD.requirement_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.requirement_code_normalized<>upper(NEW.requirement_code)
       OR NOT (
         (OLD.requirement_state='ACTIVE' AND NEW.requirement_state='ACTIVE'
          AND NEW.requirement_code<>OLD.requirement_code)
         OR (OLD.requirement_state='ACTIVE' AND NEW.requirement_state IN ('DEFERRED','REJECTED')
             AND NEW.requirement_code=OLD.requirement_code)
         OR (OLD.requirement_state<>'ARCHIVED' AND NEW.requirement_state='ARCHIVED'
             AND NEW.requirement_code=OLD.requirement_code)
       ) THEN RAISE EXCEPTION 'Requirement identity mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Requirement identity table';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_requirement_version_create_results",
        sa.Column("requirement_version_id", ident, primary_key=True),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("requirement_id", "lock_version",
                            name="uq_req_version_create_results__requirement_lock"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_version_create_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_req_version_create_results__actor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("expected_lock_version>=0 AND lock_version=expected_lock_version+1",
                           name="ck_req_version_create_results__lock"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_req_version_create_results__fingerprint"),
        schema="plm",
    )
    op.execute(_OWNER_GUARDS)
    op.execute("CREATE TRIGGER trg_req_requirement_version_create_results__immutable BEFORE INSERT OR UPDATE OR DELETE ON plm.req_requirement_version_create_results FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_version_create_result()")
    op.execute("CREATE TRIGGER trg_req_requirement_version_create_results__no_truncate BEFORE TRUNCATE ON plm.req_requirement_version_create_results FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_requirement_version_create_result_truncate()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_req_requirement_versions__create_closure AFTER INSERT ON plm.req_requirement_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_requirement_version_create_closure()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RequirementVersion owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_requirement_version_create_results)"
    )).scalar_one():
        raise RuntimeError("RequirementVersion create history prevents downgrade")
    op.execute("DROP TRIGGER trg_req_requirement_versions__create_closure ON plm.req_requirement_versions")
    op.execute("DROP TRIGGER trg_req_requirement_version_create_results__immutable ON plm.req_requirement_version_create_results")
    op.execute("DROP TRIGGER trg_req_requirement_version_create_results__no_truncate ON plm.req_requirement_version_create_results")
    op.execute(_CLOSED_GUARDS)
    op.drop_table("req_requirement_version_create_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_version_create_result()")
    op.execute("DROP FUNCTION plm.reject_requirement_version_create_result_truncate()")
    op.execute("DROP FUNCTION plm.enforce_requirement_version_create_closure()")
