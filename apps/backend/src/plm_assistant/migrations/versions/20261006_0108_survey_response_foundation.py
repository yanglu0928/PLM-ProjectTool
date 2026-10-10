"""Add SRV-04 Survey Assignment/Response foundation.

Revision ID: 20261006_0108
Revises: 20261006_0107
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261006_0108"
down_revision = "20261006_0107"
branch_labels = None
depends_on = None

_TABLES = (
    "srv_assignments", "srv_responses", "srv_answers",
    "srv_answer_evidence_refs",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_response_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  assignment_row plm.srv_assignments%ROWTYPE;
  prior_response plm.srv_responses%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='srv_assignments' THEN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Survey Assignment history is immutable'; END IF;
    IF TG_OP='INSERT' THEN
      IF NEW.submission_state<>'ASSIGNED' OR NEW.lock_version<>0
         OR NEW.updated_by IS NOT NULL OR NEW.submitted_by IS NOT NULL
         OR NEW.submitted_at IS NOT NULL OR NEW.validated_by IS NOT NULL
         OR NEW.validated_at IS NOT NULL OR NEW.returned_by IS NOT NULL
         OR NEW.returned_at IS NOT NULL OR NEW.return_comment IS NOT NULL THEN
        RAISE EXCEPTION 'Survey Assignment initial state is invalid';
      END IF;
      IF NOT EXISTS (
           SELECT 1 FROM plm.srv_rounds r
           JOIN plm.srv_target_departments t
             ON t.survey_version_id=r.survey_version_id
            AND t.department_id=NEW.department_id
           JOIN plm.prj_departments d
             ON d.department_id=t.department_id AND d.project_id=r.project_id
           WHERE r.survey_round_id=NEW.survey_round_id
             AND ROW(r.survey_id,r.survey_version_id,r.project_id)
                 IS NOT DISTINCT FROM
                 ROW(NEW.survey_id,NEW.survey_version_id,NEW.project_id)
             AND r.round_state='OPEN' AND d.state='ACTIVE') THEN
        RAISE EXCEPTION 'Survey Assignment requires an open matching Round target';
      END IF;
      IF NEW.assignee_user_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM plm.prj_project_members m
           WHERE m.project_id=NEW.project_id AND m.user_id=NEW.assignee_user_id
             AND m.department_id=NEW.department_id AND m.state='ACTIVE') THEN
        RAISE EXCEPTION 'Survey Assignment assignee is not an active target member';
      END IF;
      RETURN NEW;
    END IF;
    IF ROW(NEW.survey_assignment_id,NEW.survey_round_id,NEW.survey_id,
           NEW.survey_version_id,NEW.project_id,NEW.department_id,
           NEW.assignee_user_id,NEW.created_by,NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.survey_assignment_id,OLD.survey_round_id,OLD.survey_id,
           OLD.survey_version_id,OLD.project_id,OLD.department_id,
           OLD.assignee_user_id,OLD.created_by,OLD.created_at)
       OR NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_by IS NULL
       OR NEW.updated_at<OLD.updated_at THEN
      RAISE EXCEPTION 'Survey Assignment update projection is invalid';
    END IF;
    IF NOT (
      (OLD.submission_state='ASSIGNED' AND NEW.submission_state='IN_PROGRESS') OR
      (OLD.submission_state='IN_PROGRESS' AND NEW.submission_state='IN_PROGRESS') OR
      (OLD.submission_state='IN_PROGRESS' AND NEW.submission_state='SUBMITTED') OR
      (OLD.submission_state='SUBMITTED' AND NEW.submission_state='VALIDATED') OR
      (OLD.submission_state='SUBMITTED' AND NEW.submission_state='RETURNED') OR
      (OLD.submission_state='RETURNED' AND NEW.submission_state='IN_PROGRESS')
    ) THEN RAISE EXCEPTION 'Survey Assignment state transition is invalid'; END IF;
    IF NOT EXISTS (
         SELECT 1 FROM plm.srv_rounds r WHERE r.survey_round_id=NEW.survey_round_id
           AND r.project_id=NEW.project_id AND r.round_state='OPEN') THEN
      RAISE EXCEPTION 'Survey Assignment requires an open matching Round target';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Survey Response history is immutable'; END IF;

  IF TG_TABLE_NAME='srv_responses' THEN
    SELECT * INTO assignment_row FROM plm.srv_assignments
     WHERE survey_assignment_id=NEW.survey_assignment_id FOR SHARE;
    IF assignment_row.survey_assignment_id IS NULL
       OR ROW(assignment_row.survey_round_id,assignment_row.survey_id,
              assignment_row.survey_version_id,assignment_row.project_id)
          IS DISTINCT FROM
          ROW(NEW.survey_round_id,NEW.survey_id,NEW.survey_version_id,NEW.project_id)
       OR assignment_row.submission_state NOT IN ('ASSIGNED','IN_PROGRESS','RETURNED')
       OR NOT EXISTS (SELECT 1 FROM plm.srv_rounds r
                      WHERE r.survey_round_id=NEW.survey_round_id
                        AND r.project_id=NEW.project_id AND r.round_state='OPEN') THEN
      RAISE EXCEPTION 'Survey Response requires a writable matching Assignment';
    END IF;
    IF NEW.correction_of_response_id IS NOT NULL THEN
      SELECT * INTO prior_response FROM plm.srv_responses
       WHERE survey_response_id=NEW.correction_of_response_id FOR SHARE;
      IF prior_response.survey_response_id IS NULL
         OR ROW(prior_response.survey_assignment_id,prior_response.question_row_id)
            IS DISTINCT FROM ROW(NEW.survey_assignment_id,NEW.question_row_id) THEN
        RAISE EXCEPTION 'Survey Response correction chain is invalid';
      END IF;
    END IF;
    IF NEW.response_source='FACILITATED_RECORD' AND NOT EXISTS (
         SELECT 1 FROM plm.srv_round_source_records s
         WHERE s.round_source_record_ref_id=NEW.round_source_record_ref_id
           AND s.survey_round_id=NEW.survey_round_id
           AND s.project_id=NEW.project_id
           AND s.question_row_id=NEW.question_row_id) THEN
      RAISE EXCEPTION 'Facilitated Survey Response source is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME='srv_answer_evidence_refs' THEN
    IF NOT EXISTS (
         SELECT 1 FROM plm.evd_evidence_records e
         JOIN plm.doc_document_versions v
           ON v.document_version_id=e.document_version_id AND v.document_id=e.document_id
         JOIN plm.doc_documents d ON d.document_id=v.document_id
         WHERE e.evidence_id=NEW.evidence_id AND e.scope='PROJECT'
           AND e.project_id=NEW.project_id AND e.eligibility_state='ELIGIBLE'
           AND e.lock_version=NEW.observed_evidence_lock_version
           AND e.content_fingerprint=NEW.content_fingerprint
           AND e.document_id=NEW.document_id
           AND e.document_version_id=NEW.document_version_id
           AND v.scope='PROJECT' AND v.project_id=NEW.project_id
           AND v.availability_state='AVAILABLE'
           AND d.scope='PROJECT' AND d.project_id=NEW.project_id
           AND d.document_state='ACTIVE') THEN
      RAISE EXCEPTION 'Survey Answer Evidence snapshot is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.ensure_survey_response_answer()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM plm.srv_answers a
                 WHERE a.survey_response_id=NEW.survey_response_id) THEN
    RAISE EXCEPTION 'Survey Response requires exactly one Answer';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_survey_response_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Survey Response history cannot be truncated'; END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "srv_assignments",
        sa.Column("survey_assignment_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_round_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("department_id", ident, nullable=False),
        sa.Column("assignee_user_id", ident),
        sa.Column("submission_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ASSIGNED'")),
        sa.Column("submitted_by", ident), sa.Column("submitted_at", timestamp),
        sa.Column("validated_by", ident), sa.Column("validated_at", timestamp),
        sa.Column("returned_by", ident), sa.Column("returned_at", timestamp),
        sa.Column("return_comment", sa.Text()),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint(
            "survey_assignment_id", "survey_round_id", "survey_version_id",
            "survey_id", "project_id", name="uq_srv_assignments__identity"),
        sa.UniqueConstraint(
            "survey_round_id", "department_id", "assignee_user_id",
            name="uq_srv_assignments__round_target",
            postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(
            ["survey_round_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_rounds.survey_round_id",
             "plm.srv_rounds.survey_version_id", "plm.srv_rounds.survey_id",
             "plm.srv_rounds.project_id"], name="fk_srv_assignments__round",
            ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["survey_version_id", "department_id"],
            ["plm.srv_target_departments.survey_version_id",
             "plm.srv_target_departments.department_id"],
            name="fk_srv_assignments__target", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_assignments__department", ondelete="NO ACTION"),
        *[sa.ForeignKeyConstraint([column], ["plm.auth_users.user_id"],
                                  name=name, ondelete="NO ACTION") for column, name in (
            ("assignee_user_id", "fk_srv_assignments__assignee"),
            ("created_by", "fk_srv_assignments__creator"),
            ("updated_by", "fk_srv_assignments__updater"),
            ("submitted_by", "fk_srv_assignments__submitter"),
            ("validated_by", "fk_srv_assignments__validator"),
            ("returned_by", "fk_srv_assignments__returner"),
        )],
        sa.CheckConstraint(
            "submission_state IN ('ASSIGNED','IN_PROGRESS','SUBMITTED',"
            "'VALIDATED','RETURNED')", name="ck_srv_assignments__state"),
        sa.CheckConstraint(
            "return_comment IS NULL OR (char_length(return_comment) BETWEEN 1 AND 2000 "
            "AND return_comment=btrim(return_comment))",
            name="ck_srv_assignments__return_comment"),
        sa.CheckConstraint("lock_version>=0", name="ck_srv_assignments__lock"),
        schema="plm",
    )
    op.create_index("ix_srv_assignments__round_state", "srv_assignments",
                    ["survey_round_id", "submission_state", "survey_assignment_id"],
                    schema="plm")
    op.create_index("ix_srv_assignments__assignee_state", "srv_assignments",
                    ["assignee_user_id", "submission_state", "survey_assignment_id"],
                    schema="plm")

    op.create_table(
        "srv_responses",
        sa.Column("survey_response_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_assignment_id", ident, nullable=False),
        sa.Column("survey_round_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("question_row_id", ident, nullable=False),
        sa.Column("response_source", sa.Text(), nullable=False),
        sa.Column("round_source_record_ref_id", ident),
        sa.Column("correction_of_response_id", ident),
        sa.Column("recorded_by", ident, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "survey_response_id", "survey_assignment_id", "question_row_id",
            "project_id", name="uq_srv_responses__identity"),
        sa.UniqueConstraint(
            "survey_assignment_id", "question_row_id", "correction_of_response_id",
            name="uq_srv_responses__question_chain",
            postgresql_nulls_not_distinct=True),
        sa.UniqueConstraint("correction_of_response_id",
                            name="uq_srv_responses__correction_successor"),
        sa.ForeignKeyConstraint(
            ["survey_assignment_id", "survey_round_id", "survey_version_id",
             "survey_id", "project_id"],
            ["plm.srv_assignments.survey_assignment_id",
             "plm.srv_assignments.survey_round_id",
             "plm.srv_assignments.survey_version_id",
             "plm.srv_assignments.survey_id", "plm.srv_assignments.project_id"],
            name="fk_srv_responses__assignment", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"], name="fk_srv_responses__question",
            ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["correction_of_response_id"],
                                ["plm.srv_responses.survey_response_id"],
                                name="fk_srv_responses__correction",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["round_source_record_ref_id"],
                                ["plm.srv_round_source_records.round_source_record_ref_id"],
                                name="fk_srv_responses__round_source",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_responses__recorder", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "response_source IN ('SELF_SERVICE','FACILITATED_RECORD')",
            name="ck_srv_responses__source"),
        sa.CheckConstraint(
            "(response_source='SELF_SERVICE' AND round_source_record_ref_id IS NULL) OR "
            "(response_source='FACILITATED_RECORD' AND "
            "round_source_record_ref_id IS NOT NULL)",
            name="ck_srv_responses__source_shape"),
        sa.CheckConstraint("recorded_at<=created_at",
                           name="ck_srv_responses__recorded_at"),
        schema="plm",
    )
    op.create_index("ix_srv_responses__assignment_recorded", "srv_responses",
                    ["survey_assignment_id", "recorded_at", "survey_response_id"],
                    schema="plm")
    op.create_index("ix_srv_responses__question", "srv_responses",
                    ["question_row_id", "survey_response_id"], schema="plm")

    op.create_table(
        "srv_answers",
        sa.Column("survey_answer_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_response_id", ident, nullable=False),
        sa.Column("survey_assignment_id", ident, nullable=False),
        sa.Column("question_row_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("raw_answer", sa.Text()),
        sa.Column("answer_value", postgresql.JSONB()),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_response_id", name="uq_srv_answers__response"),
        sa.UniqueConstraint(
            "survey_answer_id", "survey_response_id", "survey_assignment_id",
            "question_row_id", "project_id", name="uq_srv_answers__identity"),
        sa.ForeignKeyConstraint(
            ["survey_response_id", "survey_assignment_id", "question_row_id",
             "project_id"],
            ["plm.srv_responses.survey_response_id",
             "plm.srv_responses.survey_assignment_id",
             "plm.srv_responses.question_row_id", "plm.srv_responses.project_id"],
            name="fk_srv_answers__response", ondelete="NO ACTION"),
        sa.CheckConstraint("raw_answer IS NOT NULL OR answer_value IS NOT NULL",
                           name="ck_srv_answers__value"),
        sa.CheckConstraint(
            "raw_answer IS NULL OR (char_length(raw_answer) BETWEEN 1 AND 20000 "
            "AND raw_answer=btrim(raw_answer))", name="ck_srv_answers__raw"),
        schema="plm",
    )

    op.create_table(
        "srv_answer_evidence_refs",
        sa.Column("survey_answer_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_answer_id", ident, nullable=False),
        sa.Column("survey_response_id", ident, nullable=False),
        sa.Column("survey_assignment_id", ident, nullable=False),
        sa.Column("question_row_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("observed_evidence_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("recorded_by", ident, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_answer_id", "ordinal",
                            name="uq_srv_answer_evidence__answer_ordinal"),
        sa.UniqueConstraint("survey_answer_id", "evidence_id",
                            name="uq_srv_answer_evidence__answer_evidence"),
        sa.ForeignKeyConstraint(
            ["survey_answer_id", "survey_response_id", "survey_assignment_id",
             "question_row_id", "project_id"],
            ["plm.srv_answers.survey_answer_id",
             "plm.srv_answers.survey_response_id",
             "plm.srv_answers.survey_assignment_id",
             "plm.srv_answers.question_row_id", "plm.srv_answers.project_id"],
            name="fk_srv_answer_evidence__answer", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_answer_evidence__document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_srv_answer_evidence__evidence",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_answer_evidence__recorder",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_answer_evidence__ordinal"),
        sa.CheckConstraint("observed_evidence_lock_version>=0",
                           name="ck_srv_answer_evidence__lock"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_srv_answer_evidence__fingerprint"),
        sa.CheckConstraint("recorded_at<=created_at",
                           name="ck_srv_answer_evidence__recorded_at"),
        schema="plm",
    )
    op.create_index("ix_srv_answer_evidence__evidence", "srv_answer_evidence_refs",
                    ["evidence_id", "survey_answer_id"], schema="plm")

    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_survey_response_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_survey_response_truncate()"
        ))
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_srv_responses__answer "
        "AFTER INSERT ON plm.srv_responses DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.ensure_survey_response_answer()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey Response downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(
                f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Survey Response history prevents downgrade")
    op.execute("DROP TRIGGER trg_srv_responses__answer ON plm.srv_responses")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.ensure_survey_response_answer()")
    op.execute("DROP FUNCTION plm.guard_survey_response_foundation()")
    op.execute("DROP FUNCTION plm.reject_survey_response_truncate()")
