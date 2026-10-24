"""Open only PRT-03 Review start and terminal transitions.

Revision ID: 20261008_0132
Revises: 20261008_0131
"""

from __future__ import annotations

import importlib
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261008_0132"
down_revision = "20261008_0131"
branch_labels = None
depends_on = None

_VERSION_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_a integer; expected_r integer; latest_no integer; latest_id uuid;
        latest_state text; root_state text; found_count integer;
BEGIN
  IF TG_TABLE_NAME='prt_prototype_versions' THEN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'PrototypeVersion history is immutable'; END IF;
    IF TG_OP='UPDATE' THEN
      IF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
           IS DISTINCT FROM
         (to_jsonb(OLD)-ARRAY['version_state','review_ref','review_round_ref'])
         OR NOT (
          (OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
           AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
           AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
          OR (OLD.version_state='IN_REVIEW' AND NEW.version_state IN ('APPROVED','RETURNED')
              AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
              AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
          OR (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
              AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
              AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
         ) THEN RAISE EXCEPTION 'PrototypeVersion update is outside Review Owner'; END IF;
      RETURN NEW;
    END IF;
    SELECT prototype_state INTO root_state FROM plm.prt_prototypes
     WHERE prototype_id=NEW.prototype_id AND project_id=NEW.project_id FOR UPDATE;
    IF NOT FOUND OR root_state<>'ACTIVE' OR NEW.version_state<>'DRAFT'
       OR NEW.review_ref IS NOT NULL OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'PrototypeVersion initial state is invalid'; END IF;
    SELECT version_no,prototype_version_id,version_state INTO latest_no,latest_id,latest_state
      FROM plm.prt_prototype_versions
     WHERE prototype_id=NEW.prototype_id AND project_id=NEW.project_id
     ORDER BY version_no DESC LIMIT 1;
    IF latest_state='IN_REVIEW' THEN
      RAISE EXCEPTION 'PrototypeVersion cannot be created during Review'; END IF;
    IF (latest_no IS NULL AND (NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
       OR (latest_no IS NOT NULL AND
           (NEW.version_no<>latest_no+1 OR NEW.supersedes_version_ref<>latest_id)) THEN
      RAISE EXCEPTION 'PrototypeVersion chain is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'PrototypeVersion history is immutable';
  ELSIF TG_TABLE_NAME='prt_version_artifact_refs' THEN
    SELECT declared_artifact_count INTO expected_a FROM plm.prt_prototype_versions
     WHERE prototype_version_id=NEW.prototype_version_id
       AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_a THEN
      RAISE EXCEPTION 'PrototypeVersion ArtifactRef is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_version_requirement_refs' THEN
    SELECT declared_requirement_count INTO expected_r FROM plm.prt_prototype_versions
     WHERE prototype_version_id=NEW.prototype_version_id
       AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_r THEN
      RAISE EXCEPTION 'PrototypeVersion RequirementRef is invalid'; END IF; RETURN NEW;
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
"""

_ROOT_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_identity_scope_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='prt_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'PrototypePackage initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'PrototypePackage history is immutable'; END IF;
    IF NEW.prototype_package_id<>OLD.prototype_package_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR NEW.package_state<>OLD.package_state
       OR OLD.package_state<>'ACTIVE' THEN RAISE EXCEPTION 'PrototypePackage mutation is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'PrototypePackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_prototypes' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.prototype_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Prototype initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'Prototype identity history is immutable'; END IF;
    IF NEW.prototype_id<>OLD.prototype_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR NOT (
         (NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
          AND ((OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE' AND NEW.name<>OLD.name)
            OR (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE' AND NEW.name=OLD.name)
            OR (OLD.prototype_state<>'ARCHIVED' AND NEW.prototype_state='ARCHIVED' AND NEW.name=OLD.name)
            OR (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='NOT_REQUIRED'
                AND OLD.current_approved_version_ref IS NULL AND NEW.name=OLD.name)))
         OR (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE'
             AND NEW.name=OLD.name AND NEW.current_approved_version_ref IS NOT NULL
             AND NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref)
       ) THEN RAISE EXCEPTION 'Prototype identity mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_scope_decisions' THEN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Prototype scope decision history is immutable'; END IF;
    IF NOT EXISTS (SELECT 1 FROM plm.prt_prototypes p
      WHERE p.prototype_id=NEW.prototype_id AND p.project_id=NEW.project_id
        AND p.prototype_state='NOT_REQUIRED' AND p.current_approved_version_ref IS NULL
        AND p.lock_version=NEW.after_version AND p.updated_by=NEW.confirmed_by) THEN
      RAISE EXCEPTION 'Prototype scope decision does not match current root'; END IF;
    IF NEW.review_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM plm.rvw_reviews r
      JOIN plm.rvw_review_rounds rr ON rr.review_id=r.review_id
       AND rr.scope=r.scope AND rr.project_id=r.project_id
      JOIN plm.rvw_subject_snapshots s ON s.review_id=r.review_id
       AND s.review_round_id=rr.review_round_id
       WHERE r.review_id=NEW.review_id AND rr.review_round_id=NEW.review_round_id
         AND r.scope='PROJECT' AND r.project_id=NEW.project_id
         AND r.subject_type='PRT_SCOPE_DECISION' AND r.subject_id=NEW.prototype_id
         AND r.review_state='APPROVED' AND rr.round_state='APPROVED'
         AND rr.subject_version_id=NEW.prototype_id
         AND s.subject_type='PRT_SCOPE_DECISION' AND s.subject_id=NEW.prototype_id
         AND s.subject_version_id=NEW.prototype_id
         AND s.content_fingerprint=NEW.decision_fingerprint
    ) THEN RAISE EXCEPTION 'Prototype scope decision Review does not match content'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_scope_decision_requirement_refs' THEN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Prototype scope decision history is immutable'; END IF;
    IF NOT EXISTS (SELECT 1 FROM plm.req_requirement_versions v
      JOIN plm.req_requirements r ON r.requirement_id=v.requirement_id AND r.project_id=v.project_id
      WHERE v.requirement_version_id=NEW.requirement_version_id
        AND v.requirement_id=NEW.requirement_id AND v.project_id=NEW.project_id
        AND v.version_state='APPROVED'
        AND r.current_approved_version_ref=v.requirement_version_id) THEN
      RAISE EXCEPTION 'Prototype scope decision RequirementVersion is not current Approved'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Prototype identity table';
END; $$;
"""

_REVIEW_GUARDS = r"""
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

CREATE OR REPLACE FUNCTION plm.guard_prototype_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE review_row plm.rvw_reviews%ROWTYPE; round_row plm.rvw_review_rounds%ROWTYPE;
DECLARE version_row plm.prt_prototype_versions%ROWTYPE; root_row plm.prt_prototypes%ROWTYPE;
DECLARE previous_row plm.prt_prototype_versions%ROWTYPE;
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Prototype Review result is immutable'; END IF;
  SELECT * INTO root_row FROM plm.prt_prototypes
   WHERE prototype_id=NEW.prototype_id AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO version_row FROM plm.prt_prototype_versions
   WHERE prototype_version_id=NEW.prototype_version_id
     AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO review_row FROM plm.rvw_reviews WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  IF root_row.prototype_id IS NULL OR root_row.prototype_state<>'ACTIVE'
     OR root_row.lock_version<>NEW.lock_version OR root_row.updated_by<>NEW.actor_id
     OR root_row.current_approved_version_ref IS DISTINCT FROM NEW.current_approved_version_ref
     OR version_row.prototype_version_id IS NULL
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'PRT-03' OR review_row.subject_id IS DISTINCT FROM NEW.prototype_id
     OR review_row.policy_code<>'PROTOTYPE_ALL_V1'
     OR round_row.review_round_id IS NULL OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.prototype_version_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'Prototype Review result does not match current facts'; END IF;
  IF NEW.event_type='START' THEN
    IF version_row.version_state<>'IN_REVIEW' OR review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_id
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.previous_approved_version_ref THEN
      RAISE EXCEPTION 'Prototype Review start result is invalid'; END IF;
  ELSIF NEW.event_type='APPROVED' THEN
    IF version_row.version_state<>'APPROVED' OR review_row.review_state<>'APPROVED'
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.prototype_version_id THEN
      RAISE EXCEPTION 'Prototype Review approval result is invalid'; END IF;
    IF NEW.previous_approved_version_ref IS NOT NULL THEN
      SELECT * INTO previous_row FROM plm.prt_prototype_versions
       WHERE prototype_version_id=NEW.previous_approved_version_ref
         AND prototype_id=NEW.prototype_id AND project_id=NEW.project_id FOR SHARE;
      IF previous_row.prototype_version_id IS NULL OR previous_row.version_state<>'SUPERSEDED'
         OR previous_row.version_no>=version_row.version_no THEN
        RAISE EXCEPTION 'Prototype previous approval was not superseded'; END IF; END IF;
  ELSIF NEW.event_type IN ('RETURNED','WITHDRAWN') THEN
    IF version_row.version_state<>'RETURNED' OR review_row.review_state<>NEW.event_type
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.previous_approved_version_ref THEN
      RAISE EXCEPTION 'Prototype Review nonapproval result is invalid'; END IF;
  ELSE RAISE EXCEPTION 'Prototype Review result event is invalid'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_review_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Prototype Review result history cannot be truncated';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_prototype_review_version_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW' THEN
    IF EXISTS (SELECT 1 FROM plm.prt_version_review_state_results x
      WHERE x.prototype_version_id=NEW.prototype_version_id AND x.event_type='START'
        AND x.review_id=NEW.review_ref AND x.review_round_id=NEW.review_round_ref) THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='IN_REVIEW' AND NEW.version_state IN ('APPROVED','RETURNED') THEN
    IF EXISTS (SELECT 1 FROM plm.prt_version_review_state_results x
      WHERE x.prototype_version_id=NEW.prototype_version_id
        AND x.event_type=CASE WHEN NEW.version_state='APPROVED' THEN 'APPROVED'
          ELSE (SELECT review_state FROM plm.rvw_reviews WHERE review_id=NEW.review_ref) END
        AND x.review_id=NEW.review_ref AND x.review_round_id=NEW.review_round_ref) THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED' THEN
    IF EXISTS (SELECT 1 FROM plm.prt_version_review_state_results x
      WHERE x.previous_approved_version_ref=NEW.prototype_version_id AND x.event_type='APPROVED')
      THEN RETURN NULL; END IF;
  END IF;
  RAISE EXCEPTION 'PrototypeVersion Review transition has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_prototype_review_root_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
     AND EXISTS (SELECT 1 FROM plm.prt_version_review_state_results x
       WHERE x.prototype_id=NEW.prototype_id AND x.project_id=NEW.project_id
         AND x.lock_version=NEW.lock_version AND x.actor_id=NEW.updated_by
         AND x.event_type='APPROVED'
         AND x.current_approved_version_ref=NEW.current_approved_version_ref
         AND x.previous_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref)
    THEN RETURN NULL; END IF;
  IF NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
     THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Prototype approval pointer has no immutable result';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "prt_version_review_state_results",
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
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
        sa.UniqueConstraint("prototype_id", "lock_version",
                            name="uq_prt_review_results__prototype_lock"),
        sa.UniqueConstraint("prototype_version_id", "event_type",
                            name="uq_prt_review_results__version_event"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["previous_approved_version_ref", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_review_results__previous", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["current_approved_version_ref", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_review_results__current", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_prt_review_results__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_prt_review_results__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_prt_review_results__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("event_type IN ('START','APPROVED','RETURNED','WITHDRAWN')",
                           name="ck_prt_review_results__event"),
        sa.CheckConstraint("expected_lock_version>=0 AND lock_version=expected_lock_version+1",
                           name="ck_prt_review_results__lock"),
        sa.CheckConstraint(
            "(event_type='APPROVED' AND current_approved_version_ref=prototype_version_id) "
            "OR (event_type<>'APPROVED' AND current_approved_version_ref IS NOT DISTINCT "
            "FROM previous_approved_version_ref)", name="ck_prt_review_results__pointer"),
        schema="plm")
    op.create_index("ix_prt_review_results__review_round",
                    "prt_version_review_state_results", ["review_id", "review_round_id"],
                    schema="plm")
    op.execute(sa.text(_VERSION_GUARD + _ROOT_GUARD + _REVIEW_GUARDS))
    op.execute("CREATE TRIGGER trg_prt_review_results__immutable BEFORE INSERT OR UPDATE OR DELETE ON plm.prt_version_review_state_results FOR EACH ROW EXECUTE FUNCTION plm.guard_prototype_review_state_result()")
    op.execute("CREATE TRIGGER trg_prt_review_results__no_truncate BEFORE TRUNCATE ON plm.prt_version_review_state_results FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_prototype_review_result_truncate()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_prt_versions__review_closure AFTER UPDATE ON plm.prt_prototype_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_prototype_review_version_closure()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_prt_prototypes__review_closure AFTER UPDATE ON plm.prt_prototypes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_prototype_review_root_closure()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype Review downgrade is disabled")
    op.execute("LOCK TABLE plm.prt_prototypes, plm.prt_prototype_versions, plm.prt_version_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_version_review_state_results) "
        "OR EXISTS (SELECT 1 FROM plm.prt_prototypes WHERE current_approved_version_ref IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.prt_prototype_versions WHERE version_state<>'DRAFT' "
        "OR review_ref IS NOT NULL OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Prototype Review history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_prototypes__review_closure ON plm.prt_prototypes")
    op.execute("DROP TRIGGER trg_prt_versions__review_closure ON plm.prt_prototype_versions")
    op.execute("DROP TRIGGER trg_prt_review_results__immutable ON plm.prt_version_review_state_results")
    op.execute("DROP TRIGGER trg_prt_review_results__no_truncate ON plm.prt_version_review_state_results")
    op.drop_index("ix_prt_review_results__review_round",
                  table_name="prt_version_review_state_results", schema="plm")
    op.drop_table("prt_version_review_state_results", schema="plm")
    for function in (
        "enforce_prototype_review_root_closure", "enforce_prototype_review_version_closure",
        "guard_prototype_review_state_result", "reject_prototype_review_result_truncate",
    ):
        op.execute(f"DROP FUNCTION plm.{function}()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261008_0131_prototype_version_create")
    identity = importlib.import_module(
        "plm_assistant.migrations.versions.20261008_0126_prototype_scope_decisions")
    op.execute(sa.text(previous._OPEN_GUARDS + identity._GUARDS))
