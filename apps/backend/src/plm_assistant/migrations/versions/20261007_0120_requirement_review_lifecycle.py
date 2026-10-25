"""Open only Requirement Review start and terminal transitions.

Revision ID: 20261007_0120
Revises: 20261007_0119
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0120"
down_revision = "20261007_0119"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_primary()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest record;
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'RequirementVersion is immutable'; END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementVersion initial state is invalid'; END IF;
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
  END IF;
  IF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
       IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['version_state','review_ref','review_round_ref'])
     OR NOT (
       (OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
        AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
        AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
       OR (OLD.version_state='IN_REVIEW'
           AND NEW.version_state IN ('APPROVED','RETURNED')
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
       OR (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
     ) THEN RAISE EXCEPTION 'RequirementVersion update is outside Review Owner'; END IF;
  RETURN NEW;
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
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.requirement_code_normalized<>upper(NEW.requirement_code)
       OR NOT (
         (NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
          AND ((OLD.requirement_state='ACTIVE' AND NEW.requirement_state='ACTIVE')
            OR (OLD.requirement_state='ACTIVE' AND NEW.requirement_state IN ('DEFERRED','REJECTED')
                AND NEW.requirement_code=OLD.requirement_code)
            OR (OLD.requirement_state<>'ARCHIVED' AND NEW.requirement_state='ARCHIVED'
                AND NEW.requirement_code=OLD.requirement_code)))
         OR (OLD.requirement_state='ACTIVE' AND NEW.requirement_state='ACTIVE'
             AND NEW.requirement_code=OLD.requirement_code
             AND NEW.current_approved_version_ref IS NOT NULL
             AND NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref)
       ) THEN RAISE EXCEPTION 'Requirement identity mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Requirement identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE review_row plm.rvw_reviews%ROWTYPE; round_row plm.rvw_review_rounds%ROWTYPE;
DECLARE version_row plm.req_requirement_versions%ROWTYPE;
DECLARE root_row plm.req_requirements%ROWTYPE; previous_row plm.req_requirement_versions%ROWTYPE;
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Requirement Review result is immutable'; END IF;
  SELECT * INTO root_row FROM plm.req_requirements
   WHERE requirement_id=NEW.requirement_id AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO version_row FROM plm.req_requirement_versions
   WHERE requirement_version_id=NEW.requirement_version_id
     AND requirement_id=NEW.requirement_id AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO review_row FROM plm.rvw_reviews WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  IF root_row.requirement_id IS NULL OR root_row.requirement_state<>'ACTIVE'
     OR root_row.lock_version<>NEW.lock_version OR root_row.updated_by<>NEW.actor_id
     OR root_row.current_approved_version_ref IS DISTINCT FROM NEW.current_approved_version_ref
     OR version_row.requirement_version_id IS NULL
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'REQ-03'
     OR review_row.subject_id IS DISTINCT FROM NEW.requirement_id
     OR review_row.policy_code<>'REQUIREMENT_ALL_V1'
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.scope<>'PROJECT' OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.requirement_version_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'Requirement Review result does not match current facts'; END IF;
  IF NEW.event_type='START' THEN
    IF version_row.version_state<>'IN_REVIEW' OR review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_id
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.previous_approved_version_ref THEN
      RAISE EXCEPTION 'Requirement Review start result is invalid'; END IF;
  ELSIF NEW.event_type='APPROVED' THEN
    IF version_row.version_state<>'APPROVED' OR review_row.review_state<>'APPROVED'
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.requirement_version_id THEN
      RAISE EXCEPTION 'Requirement Review approval result is invalid'; END IF;
    IF NEW.previous_approved_version_ref IS NOT NULL THEN
      SELECT * INTO previous_row FROM plm.req_requirement_versions
       WHERE requirement_version_id=NEW.previous_approved_version_ref
         AND requirement_id=NEW.requirement_id AND project_id=NEW.project_id FOR SHARE;
      IF previous_row.requirement_version_id IS NULL
         OR previous_row.version_state<>'SUPERSEDED'
         OR previous_row.version_no>=version_row.version_no THEN
        RAISE EXCEPTION 'Requirement previous approval was not superseded'; END IF;
    END IF;
  ELSIF NEW.event_type IN ('RETURNED','WITHDRAWN') THEN
    IF version_row.version_state<>'RETURNED'
       OR review_row.review_state<>NEW.event_type
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.previous_approved_version_ref THEN
      RAISE EXCEPTION 'Requirement Review nonapproval result is invalid'; END IF;
  ELSE RAISE EXCEPTION 'Requirement Review result event is invalid'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_review_state_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Requirement Review result history cannot be truncated';
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
  ) OR EXISTS (
    SELECT 1 FROM plm.req_requirement_review_state_results x
     WHERE x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.lock_version=NEW.lock_version AND x.actor_id=NEW.updated_by
       AND x.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
  ) THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Requirement mutation has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_review_version_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW' THEN
    IF EXISTS (SELECT 1 FROM plm.req_requirement_review_state_results x
      WHERE x.requirement_version_id=NEW.requirement_version_id
        AND x.event_type='START' AND x.review_id=NEW.review_ref
        AND x.review_round_id=NEW.review_round_ref) THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='IN_REVIEW' AND NEW.version_state IN ('APPROVED','RETURNED') THEN
    IF EXISTS (SELECT 1 FROM plm.req_requirement_review_state_results x
      WHERE x.requirement_version_id=NEW.requirement_version_id
        AND x.event_type=CASE WHEN NEW.version_state='APPROVED' THEN 'APPROVED'
          ELSE (SELECT review_state FROM plm.rvw_reviews WHERE review_id=NEW.review_ref) END
        AND x.review_id=NEW.review_ref AND x.review_round_id=NEW.review_round_ref)
      THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED' THEN
    IF EXISTS (SELECT 1 FROM plm.req_requirement_review_state_results x
      WHERE x.previous_approved_version_ref=NEW.requirement_version_id
        AND x.event_type='APPROVED') THEN RETURN NULL; END IF;
  END IF;
  RAISE EXCEPTION 'RequirementVersion Review transition has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_requirement_review_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root_row plm.req_requirements%ROWTYPE; current_row plm.req_requirement_versions%ROWTYPE;
DECLARE review_row plm.rvw_reviews%ROWTYPE; round_row plm.rvw_review_rounds%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='req_requirements' THEN root_row:=NEW;
  ELSE SELECT * INTO root_row FROM plm.req_requirements
    WHERE requirement_id=NEW.requirement_id AND project_id=NEW.project_id FOR SHARE; END IF;
  IF root_row.requirement_id IS NULL THEN RAISE EXCEPTION 'Requirement Review root is missing'; END IF;
  IF root_row.current_approved_version_ref IS NOT NULL THEN
    SELECT * INTO current_row FROM plm.req_requirement_versions
     WHERE requirement_version_id=root_row.current_approved_version_ref
       AND requirement_id=root_row.requirement_id AND project_id=root_row.project_id FOR SHARE;
    IF current_row.requirement_version_id IS NULL OR current_row.version_state<>'APPROVED' THEN
      RAISE EXCEPTION 'Requirement approved pointer is invalid'; END IF;
  END IF;
  IF TG_TABLE_NAME='req_requirements' THEN RETURN NULL; END IF;
  IF NEW.version_state='DRAFT' THEN RETURN NULL; END IF;
  IF NEW.version_state='SUPERSEDED' THEN
    IF current_row.requirement_version_id IS NULL
       OR current_row.requirement_version_id=NEW.requirement_version_id
       OR current_row.version_no<=NEW.version_no THEN
      RAISE EXCEPTION 'Requirement superseded version is invalid'; END IF; RETURN NULL;
  END IF;
  SELECT * INTO review_row FROM plm.rvw_reviews WHERE review_id=NEW.review_ref FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_ref FOR SHARE;
  IF review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'REQ-03'
     OR review_row.subject_id IS DISTINCT FROM NEW.requirement_id
     OR review_row.policy_code<>'REQUIREMENT_ALL_V1'
     OR round_row.review_round_id IS NULL OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'PROJECT' OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.requirement_version_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'Requirement Review binding is invalid'; END IF;
  IF NEW.version_state='IN_REVIEW' THEN
    IF review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_ref THEN
      RAISE EXCEPTION 'Requirement Review start is invalid'; END IF;
  ELSIF NEW.version_state='APPROVED' THEN
    IF review_row.review_state<>'APPROVED' OR review_row.active_round_id IS NOT NULL
       OR root_row.current_approved_version_ref IS DISTINCT FROM NEW.requirement_version_id THEN
      RAISE EXCEPTION 'Requirement approval formalization is incomplete'; END IF;
  ELSIF NEW.version_state='RETURNED' THEN
    IF review_row.review_state NOT IN ('RETURNED','WITHDRAWN')
       OR review_row.active_round_id IS NOT NULL
       OR root_row.current_approved_version_ref IS NOT DISTINCT FROM NEW.requirement_version_id THEN
      RAISE EXCEPTION 'Requirement nonapproval formalization is invalid'; END IF;
  ELSE RAISE EXCEPTION 'Requirement Review version state is invalid'; END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_requirement_review_state_results",
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("review_id", ident, nullable=False),
        sa.Column("review_round_id", ident, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("previous_approved_version_ref", ident),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("requirement_id", "lock_version",
                            name="uq_req_review_results__requirement_lock"),
        sa.UniqueConstraint("requirement_version_id", "event_type",
                            name="uq_req_review_results__version_event"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["previous_approved_version_ref", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_review_results__previous", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["current_approved_version_ref", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_review_results__current", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_req_review_results__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_req_review_results__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_req_review_results__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("event_type IN ('START','APPROVED','RETURNED','WITHDRAWN')",
                           name="ck_req_review_results__event"),
        sa.CheckConstraint("expected_lock_version>=0 AND lock_version=expected_lock_version+1",
                           name="ck_req_review_results__lock"),
        sa.CheckConstraint(
            "(event_type='APPROVED' AND current_approved_version_ref=requirement_version_id) "
            "OR (event_type<>'APPROVED' AND current_approved_version_ref IS NOT DISTINCT "
            "FROM previous_approved_version_ref)",
            name="ck_req_review_results__pointer"),
        schema="plm",
    )
    op.create_index("ix_req_review_results__review_round",
                    "req_requirement_review_state_results",
                    ["review_id", "review_round_id"], schema="plm")
    op.execute(sa.text(_GUARDS))
    op.execute("CREATE TRIGGER trg_req_review_results__immutable BEFORE INSERT OR UPDATE OR DELETE ON plm.req_requirement_review_state_results FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_review_state_result()")
    op.execute("CREATE TRIGGER trg_req_review_results__no_truncate BEFORE TRUNCATE ON plm.req_requirement_review_state_results FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_requirement_review_state_result_truncate()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_req_versions__review_closure AFTER UPDATE ON plm.req_requirement_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_requirement_review_version_closure()")
    for table in ("req_requirements", "req_requirement_versions"):
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__review_integrity "
            f"AFTER UPDATE ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION plm.validate_requirement_review_integrity()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement Review downgrade is disabled")
    op.execute("LOCK TABLE plm.req_requirements, plm.req_requirement_versions, plm.req_requirement_review_state_results, plm.rvw_reviews, plm.rvw_review_rounds IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_requirement_review_state_results) "
        "OR EXISTS (SELECT 1 FROM plm.req_requirements WHERE current_approved_version_ref IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.req_requirement_versions WHERE version_state<>'DRAFT' "
        "OR review_ref IS NOT NULL OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Requirement Review history prevents downgrade")
    for table in reversed(("req_requirements", "req_requirement_versions")):
        op.execute(sa.text(
            f"DROP TRIGGER trg_{table}__review_integrity ON plm.{table}"
        ))
    op.execute("DROP TRIGGER trg_req_versions__review_closure ON plm.req_requirement_versions")
    op.execute("DROP TRIGGER trg_req_review_results__immutable ON plm.req_requirement_review_state_results")
    op.execute("DROP TRIGGER trg_req_review_results__no_truncate ON plm.req_requirement_review_state_results")
    op.drop_index("ix_req_review_results__review_round",
                  table_name="req_requirement_review_state_results", schema="plm")
    op.drop_table("req_requirement_review_state_results", schema="plm")
    op.execute("DROP FUNCTION plm.validate_requirement_review_integrity()")
    op.execute("DROP FUNCTION plm.enforce_requirement_review_version_closure()")
    op.execute("DROP FUNCTION plm.guard_requirement_review_state_result()")
    op.execute("DROP FUNCTION plm.reject_requirement_review_state_result_truncate()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261007_0119_requirement_version_create_owner"
    )
    op.execute(sa.text(previous._OWNER_GUARDS))
