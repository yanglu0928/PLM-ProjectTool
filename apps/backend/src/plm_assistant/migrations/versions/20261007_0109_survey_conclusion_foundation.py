"""Add SRV-05 SurveyConclusion immutable version foundation.

Revision ID: 20261007_0109
Revises: 20261006_0108
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0109"
down_revision = "20261006_0108"
branch_labels = None
depends_on = None

_TABLES = (
    "srv_conclusions", "srv_department_conclusions", "srv_module_conclusions",
    "srv_conclusion_evidence_refs", "srv_conclusion_open_issues",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_conclusion_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  prior_row plm.srv_conclusions%ROWTYPE;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Survey Conclusion history is immutable';
  END IF;

  IF TG_TABLE_NAME='srv_conclusions' THEN
    IF NEW.conclusion_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'Survey Conclusion initial state is invalid';
    END IF;
    IF (NEW.version_no=1) IS DISTINCT FROM (NEW.supersedes_ref IS NULL) THEN
      RAISE EXCEPTION 'Survey Conclusion version chain is invalid';
    END IF;
    IF NEW.supersedes_ref IS NOT NULL THEN
      SELECT * INTO prior_row FROM plm.srv_conclusions
       WHERE survey_conclusion_id=NEW.supersedes_ref FOR SHARE;
      IF prior_row.survey_conclusion_id IS NULL
         OR prior_row.survey_id IS DISTINCT FROM NEW.survey_id
         OR prior_row.version_no+1<>NEW.version_no THEN
        RAISE EXCEPTION 'Survey Conclusion supersedes chain is invalid';
      END IF;
    END IF;
    IF (SELECT count(*) FROM plm.srv_rounds r
        WHERE r.survey_round_id=ANY(NEW.round_refs)
          AND r.project_id=NEW.project_id AND r.survey_id=NEW.survey_id
          AND r.round_state='CLOSED')<>cardinality(NEW.round_refs) THEN
      RAISE EXCEPTION 'Survey Conclusion requires closed matching Rounds';
    END IF;
    IF cardinality(NEW.ai_task_refs)>0 AND
       (SELECT count(*) FROM plm.ai_tasks t
        WHERE t.ai_task_id=ANY(NEW.ai_task_refs) AND t.scope='PROJECT'
          AND t.project_id=NEW.project_id AND t.task_type='SURVEY_ANALYZE'
          AND t.task_state='SUCCEEDED')<>cardinality(NEW.ai_task_refs) THEN
      RAISE EXCEPTION 'Survey Conclusion AI provenance is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME='srv_department_conclusions'
     OR TG_TABLE_NAME='srv_module_conclusions' THEN
    IF cardinality(NEW.response_refs)>0 AND
       (SELECT count(*) FROM plm.srv_responses r
        JOIN plm.srv_assignments a
          ON a.survey_assignment_id=r.survey_assignment_id
         AND a.project_id=r.project_id
        WHERE r.survey_response_id=ANY(NEW.response_refs)
          AND r.project_id=NEW.project_id
          AND a.submission_state='VALIDATED'
          AND NOT EXISTS (
            SELECT 1 FROM plm.srv_responses successor
             WHERE successor.correction_of_response_id=r.survey_response_id
          ))<>cardinality(NEW.response_refs) THEN
      RAISE EXCEPTION 'Survey Conclusion Response snapshot is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME='srv_conclusion_evidence_refs' THEN
    IF NOT EXISTS (
         SELECT 1 FROM plm.evd_evidence_records e
         JOIN plm.doc_document_versions v
           ON v.document_version_id=e.document_version_id
          AND v.document_id=e.document_id
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
      RAISE EXCEPTION 'Survey Conclusion Evidence snapshot is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME='srv_conclusion_open_issues' THEN
    IF NOT EXISTS (
         SELECT 1 FROM plm.hnd_action_items a
          WHERE a.action_item_id=NEW.issue_id AND a.project_id=NEW.project_id
            AND a.action_state=NEW.observed_issue_state
            AND a.lock_version=NEW.observed_lock_version) THEN
      RAISE EXCEPTION 'Survey Conclusion open issue snapshot is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.ensure_survey_conclusion_collections()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT count(*) FROM plm.srv_department_conclusions d
      WHERE d.survey_conclusion_id=NEW.survey_conclusion_id)
       <>NEW.declared_department_count
     OR (SELECT count(*) FROM plm.srv_module_conclusions m
         WHERE m.survey_conclusion_id=NEW.survey_conclusion_id)
       <>NEW.declared_module_count
     OR (SELECT count(*) FROM plm.srv_conclusion_evidence_refs e
         WHERE e.survey_conclusion_id=NEW.survey_conclusion_id)
       <>NEW.declared_evidence_count
     OR (SELECT count(*) FROM plm.srv_conclusion_open_issues i
         WHERE i.survey_conclusion_id=NEW.survey_conclusion_id)
       <>NEW.declared_open_issue_count THEN
    RAISE EXCEPTION 'Survey Conclusion declared collections mismatch';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_survey_conclusion_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Survey Conclusion history cannot be truncated'; END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    uuid_array = postgresql.ARRAY(ident)
    op.create_table(
        "srv_conclusions",
        sa.Column("survey_conclusion_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("conclusion_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("round_refs", uuid_array, nullable=False),
        sa.Column("ai_task_refs", uuid_array, nullable=False,
                  server_default=sa.text("'{}'::uuid[]")),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("conclusion_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_department_count", sa.Integer(), nullable=False),
        sa.Column("declared_module_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_count", sa.Integer(), nullable=False),
        sa.Column("declared_open_issue_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_conclusion_id", "conclusion_series_id",
                            "project_id", name="uq_srv_conclusions__identity"),
        sa.UniqueConstraint("conclusion_series_id", "version_no",
                            name="uq_srv_conclusions__series_no"),
        sa.ForeignKeyConstraint(
            ["survey_id", "project_id"],
            ["plm.srv_surveys.survey_id", "plm.srv_surveys.project_id"],
            name="fk_srv_conclusions__survey", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_ref", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusions__supersedes", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_srv_conclusions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"],
                                ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_srv_conclusions__review_round",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_conclusions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_srv_conclusions__number"),
        sa.CheckConstraint(
            "conclusion_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_srv_conclusions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_srv_conclusions__fingerprint"),
        sa.CheckConstraint(
            "cardinality(round_refs)>0 AND array_position(round_refs,NULL) IS NULL "
            "AND array_position(ai_task_refs,NULL) IS NULL",
            name="ck_srv_conclusions__refs"),
        sa.CheckConstraint(
            "declared_department_count>=0 AND declared_module_count>=0 "
            "AND declared_department_count+declared_module_count>0 "
            "AND declared_evidence_count>0 AND declared_open_issue_count>=0",
            name="ck_srv_conclusions__counts"),
        sa.CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_srv_conclusions__review_shape"),
        schema="plm",
    )
    op.create_index("ix_srv_conclusions__project_created", "srv_conclusions",
                    ["project_id", "created_at", "survey_conclusion_id"], schema="plm")
    op.create_index("ix_srv_conclusions__series_version", "srv_conclusions",
                    ["project_id", "conclusion_series_id", "version_no"], schema="plm")
    op.create_index("uq_srv_conclusions__series_in_review", "srv_conclusions",
                    ["conclusion_series_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("conclusion_state='IN_REVIEW'"))
    op.create_index("uq_srv_conclusions__series_approved", "srv_conclusions",
                    ["conclusion_series_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("conclusion_state='APPROVED'"))

    op.create_table(
        "srv_department_conclusions",
        sa.Column("department_conclusion_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_conclusion_id", ident, nullable=False),
        sa.Column("conclusion_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("department_id", ident, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("response_refs", uuid_array, nullable=False,
                  server_default=sa.text("'{}'::uuid[]")),
        sa.Column("decision_type", sa.Text()),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decision_impact", sa.Text()),
        sa.Column("decision_evidence_id", ident),
        sa.Column("decision_review_ref", ident),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_conclusion_id", "ordinal",
                            name="uq_srv_department_conclusions__ordinal"),
        sa.UniqueConstraint("survey_conclusion_id", "department_id",
                            name="uq_srv_department_conclusions__department"),
        sa.ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_department_conclusions__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_department_conclusions__department", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decision_evidence_id"],
                                ["plm.evd_evidence_records.evidence_id"],
                                name="fk_srv_department_conclusions__decision_evidence",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decision_review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_srv_department_conclusions__decision_review",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_department_conclusions__ordinal"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                           name="ck_srv_department_conclusions__title"),
        sa.CheckConstraint("char_length(statement) BETWEEN 1 AND 20000 "
                           "AND statement=btrim(statement)",
                           name="ck_srv_department_conclusions__statement"),
        sa.CheckConstraint("array_position(response_refs,NULL) IS NULL",
                           name="ck_srv_department_conclusions__responses"),
        sa.CheckConstraint(
            "(decision_type IS NULL AND decision_reason IS NULL "
            "AND decision_impact IS NULL AND decision_evidence_id IS NULL "
            "AND decision_review_ref IS NULL) OR "
            "(decision_type IN ('SCOPE_EXCLUSION','RISK_ACCEPTANCE') "
            "AND char_length(decision_reason) BETWEEN 1 AND 2000 "
            "AND decision_reason=btrim(decision_reason) "
            "AND char_length(decision_impact) BETWEEN 1 AND 2000 "
            "AND decision_impact=btrim(decision_impact) "
            "AND decision_evidence_id IS NOT NULL AND decision_review_ref IS NOT NULL)",
            name="ck_srv_department_conclusions__decision"),
        schema="plm",
    )

    op.create_table(
        "srv_module_conclusions",
        sa.Column("module_conclusion_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_conclusion_id", ident, nullable=False),
        sa.Column("conclusion_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("module_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("response_refs", uuid_array, nullable=False,
                  server_default=sa.text("'{}'::uuid[]")),
        sa.Column("decision_type", sa.Text()),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decision_impact", sa.Text()),
        sa.Column("decision_evidence_id", ident),
        sa.Column("decision_review_ref", ident),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_conclusion_id", "ordinal",
                            name="uq_srv_module_conclusions__ordinal"),
        sa.UniqueConstraint("survey_conclusion_id", "module_key",
                            name="uq_srv_module_conclusions__key"),
        sa.ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_module_conclusions__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decision_evidence_id"],
                                ["plm.evd_evidence_records.evidence_id"],
                                name="fk_srv_module_conclusions__decision_evidence",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decision_review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_srv_module_conclusions__decision_review",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_module_conclusions__ordinal"),
        sa.CheckConstraint("module_key ~ '^[A-Z][A-Z0-9_.-]{0,63}$'",
                           name="ck_srv_module_conclusions__key"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                           name="ck_srv_module_conclusions__title"),
        sa.CheckConstraint("char_length(statement) BETWEEN 1 AND 20000 "
                           "AND statement=btrim(statement)",
                           name="ck_srv_module_conclusions__statement"),
        sa.CheckConstraint("array_position(response_refs,NULL) IS NULL",
                           name="ck_srv_module_conclusions__responses"),
        sa.CheckConstraint(
            "(decision_type IS NULL AND decision_reason IS NULL "
            "AND decision_impact IS NULL AND decision_evidence_id IS NULL "
            "AND decision_review_ref IS NULL) OR "
            "(decision_type IN ('SCOPE_EXCLUSION','RISK_ACCEPTANCE') "
            "AND char_length(decision_reason) BETWEEN 1 AND 2000 "
            "AND decision_reason=btrim(decision_reason) "
            "AND char_length(decision_impact) BETWEEN 1 AND 2000 "
            "AND decision_impact=btrim(decision_impact) "
            "AND decision_evidence_id IS NOT NULL AND decision_review_ref IS NOT NULL)",
            name="ck_srv_module_conclusions__decision"),
        schema="plm",
    )

    op.create_table(
        "srv_conclusion_evidence_refs",
        sa.Column("conclusion_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_conclusion_id", ident, nullable=False),
        sa.Column("conclusion_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("reference_role", sa.Text(), nullable=False),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("observed_evidence_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_conclusion_id", "ordinal",
                            name="uq_srv_conclusion_evidence__ordinal"),
        sa.UniqueConstraint("survey_conclusion_id", "evidence_id", "reference_role",
                            name="uq_srv_conclusion_evidence__role"),
        sa.ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusion_evidence__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_conclusion_evidence__document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_srv_conclusion_evidence__evidence",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("reference_role IN ('SUPPORT','CONFLICT')",
                           name="ck_srv_conclusion_evidence__role"),
        sa.CheckConstraint("observed_evidence_lock_version>=0",
                           name="ck_srv_conclusion_evidence__lock"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_srv_conclusion_evidence__fingerprint"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_conclusion_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_srv_conclusion_evidence__evidence",
                    "srv_conclusion_evidence_refs",
                    ["evidence_id", "survey_conclusion_id"], schema="plm")

    op.create_table(
        "srv_conclusion_open_issues",
        sa.Column("conclusion_open_issue_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_conclusion_id", ident, nullable=False),
        sa.Column("conclusion_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("issue_owner_module", sa.Text(), nullable=False),
        sa.Column("issue_object_type", sa.Text(), nullable=False),
        sa.Column("issue_id", ident, nullable=False),
        sa.Column("observed_issue_state", sa.Text(), nullable=False),
        sa.Column("observed_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("is_blocking", sa.Boolean(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_conclusion_id", "ordinal",
                            name="uq_srv_conclusion_issues__ordinal"),
        sa.UniqueConstraint("survey_conclusion_id", "issue_owner_module",
                            "issue_object_type", "issue_id",
                            name="uq_srv_conclusion_issues__issue"),
        sa.ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusion_issues__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["issue_id", "project_id"],
            ["plm.hnd_action_items.action_item_id", "plm.hnd_action_items.project_id"],
            name="fk_srv_conclusion_issues__handover_action", ondelete="NO ACTION"),
        sa.CheckConstraint("issue_owner_module='handover' AND issue_object_type='HND-03'",
                           name="ck_srv_conclusion_issues__type"),
        sa.CheckConstraint(
            "observed_issue_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED',"
            "'CLOSED','CANCELLED')", name="ck_srv_conclusion_issues__state"),
        sa.CheckConstraint("observed_lock_version>=0",
                           name="ck_srv_conclusion_issues__lock"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_conclusion_issues__ordinal"),
        schema="plm",
    )
    op.create_index("ix_srv_conclusion_issues__issue", "srv_conclusion_open_issues",
                    ["issue_id", "survey_conclusion_id"], schema="plm")

    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_survey_conclusion_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_survey_conclusion_truncate()"
        ))
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_srv_conclusions__collections "
        "AFTER INSERT ON plm.srv_conclusions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.ensure_survey_conclusion_collections()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey Conclusion downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(
                f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Survey Conclusion history prevents downgrade")
    op.execute("DROP TRIGGER trg_srv_conclusions__collections ON plm.srv_conclusions")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.ensure_survey_conclusion_collections()")
    op.execute("DROP FUNCTION plm.guard_survey_conclusion_foundation()")
    op.execute("DROP FUNCTION plm.reject_survey_conclusion_truncate()")
