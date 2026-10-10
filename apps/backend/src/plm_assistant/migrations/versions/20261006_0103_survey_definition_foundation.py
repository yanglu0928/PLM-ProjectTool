"""Add SRV-01/SRV-02 Survey identity and immutable definition foundation.

Revision ID: 20261006_0103
Revises: 20261005_0102
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261006_0103"
down_revision = "20261005_0102"
branch_labels = None
depends_on = None


_TABLES = (
    "srv_surveys", "srv_survey_versions", "srv_questions",
    "srv_question_options", "srv_question_source_refs",
    "srv_target_departments",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_definition_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Survey definition Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='srv_surveys' THEN
    IF NEW.survey_state<>'ACTIVE'
       OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'Survey initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='srv_survey_versions' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'SurveyVersion initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_survey_definition_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_version uuid;
  version_row plm.srv_survey_versions%ROWTYPE;
BEGIN
  target_version := NEW.survey_version_id;
  SELECT * INTO version_row FROM plm.srv_survey_versions
   WHERE survey_version_id=target_version;
  IF version_row.survey_version_id IS NULL THEN
    RAISE EXCEPTION 'SurveyVersion is missing';
  END IF;
  IF version_row.declared_question_count<>(
       SELECT count(*) FROM plm.srv_questions
        WHERE survey_version_id=target_version)
     OR version_row.declared_option_count<>(
       SELECT count(*) FROM plm.srv_question_options
        WHERE survey_version_id=target_version)
     OR version_row.declared_source_count<>(
       SELECT count(*) FROM plm.srv_question_source_refs
        WHERE survey_version_id=target_version)
     OR version_row.declared_target_department_count<>(
       SELECT count(*) FROM plm.srv_target_departments
        WHERE survey_version_id=target_version) THEN
    RAISE EXCEPTION 'SurveyVersion declared counts are incomplete';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_questions q
        WHERE q.survey_version_id=target_version
          AND NOT EXISTS (
              SELECT 1 FROM plm.srv_question_source_refs s
               WHERE s.question_row_id=q.question_row_id)) THEN
    RAISE EXCEPTION 'Survey question requires a source';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_questions q
        WHERE q.survey_version_id=target_version
          AND ((q.answer_type IN ('SINGLE_CHOICE','MULTIPLE_CHOICE')
                AND (SELECT count(*) FROM plm.srv_question_options o
                      WHERE o.question_row_id=q.question_row_id)<2)
               OR (q.answer_type NOT IN ('SINGLE_CHOICE','MULTIPLE_CHOICE')
                   AND EXISTS (
                       SELECT 1 FROM plm.srv_question_options o
                        WHERE o.question_row_id=q.question_row_id)))) THEN
    RAISE EXCEPTION 'Survey choice options are incomplete';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_question_source_refs s
        WHERE s.survey_version_id=target_version
          AND s.source_kind='HANDOVER_ITEM'
          AND NOT EXISTS (
              SELECT 1 FROM plm.hnd_analysis_items i
              JOIN plm.hnd_analysis_versions v
                ON v.handover_analysis_version_id=i.handover_analysis_version_id
               AND v.handover_analysis_id=i.handover_analysis_id
               AND v.project_id=i.project_id
              JOIN plm.hnd_analyses a
                ON a.handover_analysis_id=v.handover_analysis_id
               AND a.project_id=v.project_id
               AND a.current_approved_version_ref=v.handover_analysis_version_id
               WHERE i.analysis_item_row_id=s.handover_item_row_id
                 AND i.handover_analysis_version_id=s.handover_analysis_version_id
                 AND i.handover_analysis_id=s.handover_analysis_id
                 AND i.project_id=version_row.project_id
                 AND v.version_state='APPROVED' AND a.analysis_state='ACTIVE'
                 AND i.item_state IN ('CONFIRMED','RESOLVED','ACCEPTED_RISK'))) THEN
    RAISE EXCEPTION 'Survey Handover source is not a current approved project item';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_question_source_refs s
        WHERE s.survey_version_id=target_version
          AND s.source_kind='CAPABILITY_ITEM'
          AND NOT EXISTS (
              SELECT 1 FROM plm.cap_items i
              JOIN plm.cap_baseline_versions v
                ON v.baseline_version_id=i.baseline_version_id
               AND v.baseline_id=i.baseline_id
              JOIN plm.cap_baselines b
                ON b.baseline_id=v.baseline_id
               AND b.current_approved_version_ref=v.baseline_version_id
               WHERE i.capability_item_row_id=s.capability_item_row_id
                 AND i.baseline_version_id=s.capability_baseline_version_id
                 AND i.baseline_id=s.capability_baseline_id
                 AND i.item_state='AVAILABLE' AND v.version_state='APPROVED'
                 AND b.baseline_state='ACTIVE')) THEN
    RAISE EXCEPTION 'Survey Capability source is not a current approved item';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_question_source_refs s
        WHERE s.survey_version_id=target_version
          AND s.source_kind='TEMPLATE_DOCUMENT_VERSION'
          AND NOT EXISTS (
              SELECT 1 FROM plm.doc_document_versions v
              JOIN plm.doc_documents d ON d.document_id=v.document_id
               WHERE v.document_version_id=s.template_document_version_id
                 AND v.document_id=s.template_document_id
                 AND v.availability_state='AVAILABLE'
                 AND d.document_state='ACTIVE'
                 AND d.document_category='TEMPLATE'
                 AND ((v.scope='GLOBAL' AND v.project_id IS NULL
                       AND d.scope='GLOBAL' AND d.project_id IS NULL)
                      OR (v.scope='PROJECT'
                          AND v.project_id=version_row.project_id
                          AND d.scope='PROJECT'
                          AND d.project_id=version_row.project_id)))) THEN
    RAISE EXCEPTION 'Survey template source is invalid';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.srv_target_departments t
       LEFT JOIN plm.prj_departments d
         ON d.department_id=t.department_id AND d.project_id=t.project_id
        WHERE t.survey_version_id=target_version
          AND (t.project_id<>version_row.project_id OR d.department_id IS NULL
               OR d.state<>'ACTIVE')) THEN
    RAISE EXCEPTION 'Survey target department is not active in the project';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_survey_definition_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Survey definition history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "srv_surveys",
        sa.Column("survey_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("survey_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("survey_id", "project_id",
                            name="uq_srv_surveys__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_srv_surveys__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_surveys__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_surveys__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_srv_surveys__name"),
        sa.CheckConstraint("survey_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                           name="ck_srv_surveys__state"),
        sa.CheckConstraint("lock_version>=0", name="ck_srv_surveys__lock"),
        schema="plm",
    )
    op.create_index("ix_srv_surveys__project_state", "srv_surveys",
                    ["project_id", "survey_state", "survey_id"], schema="plm")
    op.create_table(
        "srv_survey_versions",
        sa.Column("survey_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_question_count", sa.Integer(), nullable=False),
        sa.Column("declared_option_count", sa.Integer(), nullable=False),
        sa.Column("declared_source_count", sa.Integer(), nullable=False),
        sa.Column("declared_target_department_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_version_id", "survey_id", "project_id",
                            name="uq_srv_versions__id_survey_project"),
        sa.UniqueConstraint("survey_id", "version_no",
                            name="uq_srv_versions__survey_no"),
        sa.ForeignKeyConstraint(
            ["survey_id", "project_id"],
            ["plm.srv_surveys.survey_id", "plm.srv_surveys.project_id"],
            name="fk_srv_versions__survey", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_versions__supersedes", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_srv_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"],
                                ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_srv_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_srv_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED',"
                           "'RETURNED','SUPERSEDED','RESTRICTED')",
                           name="ck_srv_versions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_srv_versions__fingerprint"),
        sa.CheckConstraint("declared_question_count>0 AND declared_option_count>=0 "
                           "AND declared_source_count>=declared_question_count "
                           "AND declared_target_department_count>0",
                           name="ck_srv_versions__counts"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                           "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                           name="ck_srv_versions__review_shape"),
        schema="plm",
    )
    op.create_index("ix_srv_versions__survey_created", "srv_survey_versions",
                    ["survey_id", "created_at"], schema="plm")
    op.create_index("uq_srv_versions__survey_in_review", "srv_survey_versions",
                    ["survey_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='IN_REVIEW'"))
    op.create_index("uq_srv_versions__survey_approved", "srv_survey_versions",
                    ["survey_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='APPROVED'"))
    op.create_foreign_key(
        "fk_srv_surveys__approved_version", "srv_surveys", "srv_survey_versions",
        ["current_approved_version_ref", "survey_id", "project_id"],
        ["survey_version_id", "survey_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
    )
    _create_questions(ident)
    _create_question_sources(ident)
    _create_targets(ident)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_survey_definition_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_survey_definition_truncate()"
        ))
    for table in _TABLES[1:]:
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__complete AFTER INSERT ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
            "plm.validate_survey_definition_foundation()"
        ))


def _create_questions(ident) -> None:
    op.create_table(
        "srv_questions",
        sa.Column("question_row_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("question_id", ident, nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.Text(), nullable=False),
        sa.Column("validation_rule", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("required", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("condition_rule", postgresql.JSONB()),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("evidence_required", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.UniqueConstraint("question_row_id", "survey_version_id", "survey_id",
                            "project_id", name="uq_srv_questions__row_version_survey_project"),
        sa.UniqueConstraint("survey_version_id", "question_id",
                            name="uq_srv_questions__version_stable"),
        sa.UniqueConstraint("survey_version_id", "sequence_no",
                            name="uq_srv_questions__version_sequence"),
        sa.ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_questions__version", ondelete="NO ACTION"),
        sa.CheckConstraint("sequence_no>=0", name="ck_srv_questions__sequence"),
        sa.CheckConstraint("char_length(topic) BETWEEN 1 AND 255 AND topic=btrim(topic) "
                           "AND char_length(question_text) BETWEEN 1 AND 4000 "
                           "AND question_text=btrim(question_text) "
                           "AND char_length(objective) BETWEEN 1 AND 2000 "
                           "AND objective=btrim(objective) "
                           "AND char_length(expected_output) BETWEEN 1 AND 2000 "
                           "AND expected_output=btrim(expected_output)",
                           name="ck_srv_questions__texts"),
        sa.CheckConstraint("answer_type IN ('TEXT','SINGLE_CHOICE','MULTIPLE_CHOICE',"
                           "'DATE','NUMBER','ATTACHMENT')",
                           name="ck_srv_questions__answer_type"),
        sa.CheckConstraint("jsonb_typeof(validation_rule)='object'",
                           name="ck_srv_questions__validation"),
        sa.CheckConstraint("condition_rule IS NULL OR "
                           "jsonb_typeof(condition_rule)='object'",
                           name="ck_srv_questions__condition"),
        schema="plm",
    )
    op.create_index("ix_srv_questions__version_sequence", "srv_questions",
                    ["survey_version_id", "sequence_no"], schema="plm")
    op.create_table(
        "srv_question_options",
        sa.Column("question_option_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("question_row_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("option_code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("question_row_id", "option_code",
                            name="uq_srv_options__question_code"),
        sa.UniqueConstraint("question_row_id", "ordinal",
                            name="uq_srv_options__question_ordinal"),
        sa.ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"],
            name="fk_srv_options__question", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_options__ordinal"),
        sa.CheckConstraint("option_code ~ '^[A-Z][A-Z0-9_-]{0,31}$'",
                           name="ck_srv_options__code"),
        sa.CheckConstraint("char_length(label) BETWEEN 1 AND 255 "
                           "AND label=btrim(label) AND (description IS NULL OR "
                           "(char_length(description) BETWEEN 1 AND 1000 "
                           "AND description=btrim(description)))",
                           name="ck_srv_options__texts"),
        schema="plm",
    )


def _create_question_sources(ident) -> None:
    op.create_table(
        "srv_question_source_refs",
        sa.Column("question_source_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("question_row_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("handover_item_row_id", ident),
        sa.Column("handover_analysis_version_id", ident),
        sa.Column("handover_analysis_id", ident),
        sa.Column("capability_item_row_id", ident),
        sa.Column("capability_baseline_version_id", ident),
        sa.Column("capability_baseline_id", ident),
        sa.Column("template_document_version_id", ident),
        sa.Column("template_document_id", ident),
        sa.Column("manual_source_note", sa.Text()),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("question_row_id", "ordinal",
                            name="uq_srv_question_sources__question_ordinal"),
        sa.ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"],
            name="fk_srv_question_sources__question", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["handover_item_row_id", "handover_analysis_version_id",
             "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_items.analysis_item_row_id",
             "plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.handover_analysis_id",
             "plm.hnd_analysis_items.project_id"],
            name="fk_srv_question_sources__handover_item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["capability_item_row_id", "capability_baseline_version_id",
             "capability_baseline_id"],
            ["plm.cap_items.capability_item_row_id",
             "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"],
            name="fk_srv_question_sources__capability_item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["template_document_version_id", "template_document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_question_sources__template_version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_question_sources__ordinal"),
        sa.CheckConstraint(
            "(source_kind='HANDOVER_ITEM' AND handover_item_row_id IS NOT NULL "
            "AND handover_analysis_version_id IS NOT NULL "
            "AND handover_analysis_id IS NOT NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NULL) OR "
            "(source_kind='CAPABILITY_ITEM' AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NOT NULL "
            "AND capability_baseline_version_id IS NOT NULL "
            "AND capability_baseline_id IS NOT NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NULL) OR "
            "(source_kind='TEMPLATE_DOCUMENT_VERSION' "
            "AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NOT NULL "
            "AND template_document_id IS NOT NULL AND manual_source_note IS NULL) OR "
            "(source_kind='MANUAL' AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NOT NULL "
            "AND char_length(manual_source_note) BETWEEN 1 AND 2000 "
            "AND manual_source_note=btrim(manual_source_note))",
            name="ck_srv_question_sources__shape"),
        schema="plm",
    )
    op.create_index("ix_srv_question_sources__handover", "srv_question_source_refs",
                    ["handover_item_row_id"], schema="plm")
    op.create_index("ix_srv_question_sources__capability", "srv_question_source_refs",
                    ["capability_item_row_id"], schema="plm")
    op.create_index("ix_srv_question_sources__template", "srv_question_source_refs",
                    ["template_document_version_id"], schema="plm")


def _create_targets(ident) -> None:
    op.create_table(
        "srv_target_departments",
        sa.Column("survey_target_department_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("department_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("survey_version_id", "department_id",
                            name="uq_srv_targets__version_department"),
        sa.UniqueConstraint("survey_version_id", "ordinal",
                            name="uq_srv_targets__version_ordinal"),
        sa.ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_targets__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_targets__department", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_targets__ordinal"),
        schema="plm",
    )
    op.create_index("ix_srv_targets__department", "srv_target_departments",
                    ["department_id", "survey_version_id"], schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey definition downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Survey definition history prevents downgrade")
    op.drop_constraint("fk_srv_surveys__approved_version", "srv_surveys",
                       schema="plm", type_="foreignkey")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        if table != "srv_surveys":
            op.execute(sa.text(f"DROP TRIGGER trg_{table}__complete ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_survey_definition_foundation()")
    op.execute("DROP FUNCTION plm.guard_survey_definition_foundation()")
    op.execute("DROP FUNCTION plm.reject_survey_definition_truncate()")
