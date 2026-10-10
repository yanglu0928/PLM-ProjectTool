"""Open atomic Prototype NOT_REQUIRED scope decisions.

Revision ID: 20261008_0126
Revises: 20261008_0125
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0126"
down_revision = "20261008_0125"
branch_labels = None
depends_on = None

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_identity_scope_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='prt_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'PrototypePackage initial state is invalid'; END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'PrototypePackage history is immutable'; END IF;
    IF NEW.prototype_package_id<>OLD.prototype_package_id
       OR NEW.project_id<>OLD.project_id OR NEW.created_by<>OLD.created_by
       OR NEW.created_at<>OLD.created_at OR NEW.updated_by IS NULL
       OR NEW.updated_at<>statement_timestamp() OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.package_state<>OLD.package_state OR OLD.package_state<>'ACTIVE' THEN
      RAISE EXCEPTION 'PrototypePackage mutation is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'PrototypePackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_prototypes' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.prototype_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Prototype initial state is invalid'; END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'Prototype identity history is immutable'; END IF;
    IF NEW.prototype_id<>OLD.prototype_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NOT (
         (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE'
          AND NEW.name<>OLD.name)
         OR (OLD.prototype_state<>'ARCHIVED' AND NEW.prototype_state='ARCHIVED'
             AND NEW.name=OLD.name)
         OR (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='NOT_REQUIRED'
             AND OLD.current_approved_version_ref IS NULL AND NEW.name=OLD.name)
       ) THEN RAISE EXCEPTION 'Prototype identity mutation is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_scope_decisions' THEN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Prototype scope decision history is immutable'; END IF;
    IF NOT EXISTS (
      SELECT 1 FROM plm.prt_prototypes p
       WHERE p.prototype_id=NEW.prototype_id AND p.project_id=NEW.project_id
         AND p.prototype_state='NOT_REQUIRED' AND p.current_approved_version_ref IS NULL
         AND p.lock_version=NEW.after_version AND p.updated_by=NEW.confirmed_by
    ) THEN RAISE EXCEPTION 'Prototype scope decision does not match current root'; END IF;
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
    IF NOT EXISTS (
      SELECT 1 FROM plm.req_requirement_versions v
      JOIN plm.req_requirements r ON r.requirement_id=v.requirement_id
       AND r.project_id=v.project_id
       WHERE v.requirement_version_id=NEW.requirement_version_id
         AND v.requirement_id=NEW.requirement_id AND v.project_id=NEW.project_id
         AND v.version_state='APPROVED'
         AND r.current_approved_version_ref=v.requirement_version_id
    ) THEN
      RAISE EXCEPTION 'Prototype scope decision RequirementVersion is not current Approved';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Prototype identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_prototype_command_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.prototype_state=NEW.prototype_state
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
       AND r.lock_version=NEW.lock_version
  ) AND NOT EXISTS (
    SELECT 1 FROM plm.prt_scope_decision_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND NEW.prototype_state='NOT_REQUIRED'
       AND NEW.current_approved_version_ref IS NULL
       AND r.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Prototype mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_prototype_scope_decision_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_refs uuid[];
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Prototype scope decision result history is immutable'; END IF;
  SELECT COALESCE(array_agg(x.requirement_version_id ORDER BY x.ordinal),ARRAY[]::uuid[])
    INTO actual_refs FROM plm.prt_scope_decision_requirement_refs x
   WHERE x.scope_decision_id=NEW.scope_decision_id
     AND x.prototype_id=NEW.prototype_id AND x.project_id=NEW.project_id;
  IF NEW.requirement_version_refs<>actual_refs
     OR array_position(NEW.requirement_version_refs,NULL) IS NOT NULL
     OR cardinality(NEW.requirement_version_refs)<>(
       SELECT count(DISTINCT x) FROM unnest(NEW.requirement_version_refs) x)
     OR NOT EXISTS (
       SELECT 1 FROM plm.prt_scope_decisions d
       JOIN plm.prt_prototypes p ON p.prototype_id=d.prototype_id
        AND p.project_id=d.project_id
        WHERE d.scope_decision_id=NEW.scope_decision_id
          AND d.prototype_id=NEW.prototype_id AND d.project_id=NEW.project_id
          AND d.reason=NEW.reason AND d.impact=NEW.impact
          AND d.decision_fingerprint=NEW.decision_fingerprint
          AND d.confirmed_by=NEW.confirmed_by
          AND d.review_id IS NOT DISTINCT FROM NEW.review_id
          AND d.review_round_id IS NOT DISTINCT FROM NEW.review_round_id
          AND d.after_version=NEW.lock_version AND d.decided_at=NEW.decided_at
          AND p.name=NEW.name AND p.prototype_state='NOT_REQUIRED'
          AND p.current_approved_version_ref IS NULL
          AND p.lock_version=NEW.lock_version
     ) THEN RAISE EXCEPTION 'Prototype scope decision result does not match decision'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_scope_decision_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_scope_decision_results r
     WHERE r.scope_decision_id=NEW.scope_decision_id
       AND r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.reason=NEW.reason AND r.impact=NEW.impact
       AND r.decision_fingerprint=NEW.decision_fingerprint
       AND r.confirmed_by=NEW.confirmed_by
       AND r.review_id IS NOT DISTINCT FROM NEW.review_id
       AND r.review_round_id IS NOT DISTINCT FROM NEW.review_round_id
       AND r.lock_version=NEW.after_version AND r.decided_at=NEW.decided_at
  ) OR NOT EXISTS (
    SELECT 1 FROM plm.prt_scope_decision_requirement_refs x
     WHERE x.scope_decision_id=NEW.scope_decision_id
       AND x.prototype_id=NEW.prototype_id AND x.project_id=NEW.project_id
  ) THEN RAISE EXCEPTION 'Prototype scope decision has no complete immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_scope_decision_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Prototype scope decision result history cannot be truncated';
END; $$;
"""

_DOWN_GUARDS = r"""
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
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR NOT (
         (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE' AND NEW.name<>OLD.name)
         OR (OLD.prototype_state<>'ARCHIVED' AND NEW.prototype_state='ARCHIVED'
             AND NEW.name=OLD.name)) THEN
      RAISE EXCEPTION 'Prototype identity mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME IN ('prt_scope_decisions','prt_scope_decision_requirement_refs') THEN
    RAISE EXCEPTION 'Prototype scope decision Owner is not installed';
  END IF;
  RAISE EXCEPTION 'Unknown Prototype identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_prototype_command_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.prototype_state=NEW.prototype_state
       AND r.current_approved_version_ref IS NOT DISTINCT FROM NEW.current_approved_version_ref
       AND r.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Prototype mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.add_column(
        "prt_scope_decisions",
        sa.Column("decision_fingerprint", sa.LargeBinary(), nullable=False),
        schema="plm",
    )
    op.create_check_constraint(
        "ck_prt_scope_decisions__fingerprint", "prt_scope_decisions",
        "octet_length(decision_fingerprint)=32", schema="plm",
    )
    op.create_table(
        "prt_scope_decision_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("scope_decision_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("decision_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("confirmed_by", ident, nullable=False),
        sa.Column("review_id", ident),
        sa.Column("review_round_id", ident),
        sa.Column("requirement_version_refs", postgresql.ARRAY(ident), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("decided_at", timestamp, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["scope_decision_id", "prototype_id", "project_id"],
            ["plm.prt_scope_decisions.scope_decision_id",
             "plm.prt_scope_decisions.prototype_id",
             "plm.prt_scope_decisions.project_id"],
            name="fk_prt_scope_decision_results__decision", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_prt_scope_decision_results__name"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
                           name="ck_prt_scope_decision_results__reason"),
        sa.CheckConstraint("char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
                           name="ck_prt_scope_decision_results__impact"),
        sa.CheckConstraint("octet_length(decision_fingerprint)=32",
                           name="ck_prt_scope_decision_results__fingerprint"),
        sa.CheckConstraint("cardinality(requirement_version_refs)>0",
                           name="ck_prt_scope_decision_results__requirements"),
        sa.CheckConstraint("(review_id IS NULL AND review_round_id IS NULL) OR "
                           "(review_id IS NOT NULL AND review_round_id IS NOT NULL)",
                           name="ck_prt_scope_decision_results__review_pair"),
        sa.CheckConstraint("lock_version>0",
                           name="ck_prt_scope_decision_results__version"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_prt_scope_decision_results__immutable "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.prt_scope_decision_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_prototype_scope_decision_result()"
    )
    op.execute(
        "CREATE TRIGGER trg_prt_scope_decision_results__no_truncate "
        "BEFORE TRUNCATE ON plm.prt_scope_decision_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_prototype_scope_decision_result_truncate()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_scope_decisions__closure AFTER INSERT "
        "ON plm.prt_scope_decisions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_scope_decision_closure()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype scope-decision downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_scope_decision_results) "
        "OR EXISTS (SELECT 1 FROM plm.prt_scope_decisions)"
    )).scalar_one():
        raise RuntimeError("Prototype scope decision history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_scope_decisions__closure ON plm.prt_scope_decisions")
    op.execute(
        "DROP TRIGGER trg_prt_scope_decision_results__immutable "
        "ON plm.prt_scope_decision_results"
    )
    op.execute(
        "DROP TRIGGER trg_prt_scope_decision_results__no_truncate "
        "ON plm.prt_scope_decision_results"
    )
    op.drop_table("prt_scope_decision_results", schema="plm")
    op.drop_constraint(
        "ck_prt_scope_decisions__fingerprint", "prt_scope_decisions",
        schema="plm", type_="check",
    )
    op.drop_column("prt_scope_decisions", "decision_fingerprint", schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_scope_decision_result()")
    op.execute("DROP FUNCTION plm.assert_prototype_scope_decision_closure()")
    op.execute("DROP FUNCTION plm.reject_prototype_scope_decision_result_truncate()")
    op.execute(_DOWN_GUARDS)
