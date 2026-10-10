"""Permit controlled SRV-05 review lifecycle transitions.

Revision ID: 20261007_0110
Revises: 20261007_0109
"""

from __future__ import annotations

from alembic import op


revision = "20261007_0110"
down_revision = "20261007_0109"
branch_labels = None
depends_on = None


_UP = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_conclusion_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  prior_row plm.srv_conclusions%ROWTYPE;
  payload_unchanged boolean;
BEGIN
  IF TG_OP='UPDATE' AND TG_TABLE_NAME='srv_conclusions' THEN
    payload_unchanged :=
      NEW.survey_conclusion_id IS NOT DISTINCT FROM OLD.survey_conclusion_id
      AND NEW.conclusion_series_id IS NOT DISTINCT FROM OLD.conclusion_series_id
      AND NEW.project_id IS NOT DISTINCT FROM OLD.project_id
      AND NEW.survey_id IS NOT DISTINCT FROM OLD.survey_id
      AND NEW.round_refs IS NOT DISTINCT FROM OLD.round_refs
      AND NEW.ai_task_refs IS NOT DISTINCT FROM OLD.ai_task_refs
      AND NEW.version_no IS NOT DISTINCT FROM OLD.version_no
      AND NEW.content_fingerprint IS NOT DISTINCT FROM OLD.content_fingerprint
      AND NEW.declared_department_count IS NOT DISTINCT FROM OLD.declared_department_count
      AND NEW.declared_module_count IS NOT DISTINCT FROM OLD.declared_module_count
      AND NEW.declared_evidence_count IS NOT DISTINCT FROM OLD.declared_evidence_count
      AND NEW.declared_open_issue_count IS NOT DISTINCT FROM OLD.declared_open_issue_count
      AND NEW.supersedes_ref IS NOT DISTINCT FROM OLD.supersedes_ref
      AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
      AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at;

    IF NOT payload_unchanged THEN
      RAISE EXCEPTION 'Survey Conclusion payload is immutable';
    END IF;

    IF OLD.conclusion_state='DRAFT' AND NEW.conclusion_state='IN_REVIEW'
       AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
       AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL THEN
      RETURN NEW;
    END IF;
    IF OLD.conclusion_state='IN_REVIEW'
       AND NEW.conclusion_state IN ('APPROVED','RETURNED')
       AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
       AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref THEN
      RETURN NEW;
    END IF;
    IF OLD.conclusion_state='APPROVED' AND NEW.conclusion_state='SUPERSEDED'
       AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
       AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Survey Conclusion lifecycle transition is invalid';
  END IF;

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
"""


_DOWN = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_conclusion_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_row plm.srv_conclusions%ROWTYPE;
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
          AND NOT EXISTS (SELECT 1 FROM plm.srv_responses successor
             WHERE successor.correction_of_response_id=r.survey_response_id))
          <>cardinality(NEW.response_refs) THEN
      RAISE EXCEPTION 'Survey Conclusion Response snapshot is invalid';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME='srv_conclusion_evidence_refs' THEN
    IF NOT EXISTS (SELECT 1 FROM plm.evd_evidence_records e
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
      RAISE EXCEPTION 'Survey Conclusion Evidence snapshot is invalid';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME='srv_conclusion_open_issues' AND NOT EXISTS (
      SELECT 1 FROM plm.hnd_action_items a
       WHERE a.action_item_id=NEW.issue_id AND a.project_id=NEW.project_id
         AND a.action_state=NEW.observed_issue_state
         AND a.lock_version=NEW.observed_lock_version) THEN
    RAISE EXCEPTION 'Survey Conclusion open issue snapshot is invalid';
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.execute(_UP)


def downgrade() -> None:
    op.execute(_DOWN)
