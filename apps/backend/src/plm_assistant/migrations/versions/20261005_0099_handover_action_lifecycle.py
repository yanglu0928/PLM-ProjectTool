"""Open exact Handover Action lifecycle integrity.

Revision ID: 20261005_0099
Revises: 20261005_0098
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa


revision = "20261005_0099"
down_revision = "20261005_0098"
branch_labels = None
depends_on = None

_TABLES = (
    "hnd_action_items", "hnd_action_response_refs",
    "hnd_action_evidence_refs", "hnd_action_state_events",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_action_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  action_row plm.hnd_action_items%ROWTYPE;
  allowed_transition boolean;
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Handover Action history is immutable';
  END IF;

  IF TG_TABLE_NAME='hnd_action_items' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.action_state<>'OPEN' OR NEW.lock_version<>0
         OR NEW.submitted_at IS NOT NULL OR NEW.verified_by IS NOT NULL
         OR NEW.verified_at IS NOT NULL OR NEW.closed_at IS NOT NULL
         OR NEW.resolution_trace_ref IS NOT NULL OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Handover Action initial state is invalid';
      END IF;
      RETURN NEW;
    END IF;
    IF ROW(NEW.action_item_id,NEW.project_id,NEW.source_kind,
           NEW.source_analysis_version_ref,NEW.source_item_id,NEW.human_source_reason,
           NEW.action_type,NEW.title,NEW.requested_input_spec,NEW.owner_ref,NEW.due_at,
           NEW.priority,NEW.created_by,NEW.created_reason,NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.action_item_id,OLD.project_id,OLD.source_kind,
           OLD.source_analysis_version_ref,OLD.source_item_id,OLD.human_source_reason,
           OLD.action_type,OLD.title,OLD.requested_input_spec,OLD.owner_ref,OLD.due_at,
           OLD.priority,OLD.created_by,OLD.created_reason,OLD.created_at)
       OR NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_by IS NULL
       OR NEW.updated_at<OLD.updated_at OR NEW.updated_at<NEW.created_at THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    END IF;
    allowed_transition :=
      (OLD.action_state='OPEN' AND NEW.action_state='IN_PROGRESS') OR
      (OLD.action_state='IN_PROGRESS' AND NEW.action_state='SUBMITTED') OR
      (OLD.action_state='SUBMITTED' AND NEW.action_state='VERIFIED') OR
      (OLD.action_state='VERIFIED' AND NEW.action_state='CLOSED') OR
      (OLD.action_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')
       AND NEW.action_state='CANCELLED');
    IF NOT allowed_transition THEN
      RAISE EXCEPTION 'Handover Action state transition is invalid';
    END IF;
    IF NEW.action_state='IN_PROGRESS' AND
       (NEW.submitted_at IS NOT NULL OR NEW.verified_by IS NOT NULL
        OR NEW.verified_at IS NOT NULL OR NEW.closed_at IS NOT NULL
        OR NEW.resolution_trace_ref IS NOT NULL) THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    ELSIF NEW.action_state='SUBMITTED' AND
       (NEW.submitted_at IS DISTINCT FROM NEW.updated_at
        OR NEW.verified_by IS NOT NULL OR NEW.verified_at IS NOT NULL
        OR NEW.closed_at IS NOT NULL OR NEW.resolution_trace_ref IS NOT NULL) THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    ELSIF NEW.action_state='VERIFIED' AND
       (NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
        OR NEW.verified_by IS DISTINCT FROM NEW.updated_by
        OR NEW.verified_at IS DISTINCT FROM NEW.updated_at
        OR NEW.closed_at IS NOT NULL OR NEW.resolution_trace_ref IS NOT NULL) THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    ELSIF NEW.action_state='CLOSED' AND
       (NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
        OR NEW.verified_by IS DISTINCT FROM OLD.verified_by
        OR NEW.verified_at IS DISTINCT FROM OLD.verified_at
        OR NEW.closed_at IS DISTINCT FROM NEW.updated_at
        OR NEW.resolution_trace_ref IS NULL) THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    ELSIF NEW.action_state='CANCELLED' AND
       (NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
        OR NEW.verified_by IS DISTINCT FROM OLD.verified_by
        OR NEW.verified_at IS DISTINCT FROM OLD.verified_at
        OR NEW.closed_at IS DISTINCT FROM OLD.closed_at
        OR NEW.resolution_trace_ref IS DISTINCT FROM OLD.resolution_trace_ref) THEN
      RAISE EXCEPTION 'Handover Action transition projection is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME='hnd_action_state_events' THEN
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'Handover Action state event is immutable';
    END IF;
    SELECT * INTO action_row FROM plm.hnd_action_items
     WHERE action_item_id=NEW.action_item_id FOR SHARE;
    IF action_row.action_item_id IS NULL OR NEW.project_id<>action_row.project_id THEN
      RAISE EXCEPTION 'Handover Action event scope is invalid';
    END IF;
    IF NEW.sequence_no=0 THEN
      IF NEW.from_state IS NOT NULL OR NEW.to_state<>'OPEN'
         OR NEW.actor_id<>action_row.created_by
         OR NEW.reason<>action_row.created_reason THEN
        RAISE EXCEPTION 'Handover Action initial event is invalid';
      END IF;
    ELSIF NEW.sequence_no<>action_row.lock_version+1
          OR NEW.from_state<>action_row.action_state
          OR NEW.occurred_at<action_row.updated_at
          OR NOT (
            (NEW.from_state='OPEN' AND NEW.to_state='IN_PROGRESS') OR
            (NEW.from_state='IN_PROGRESS' AND NEW.to_state='SUBMITTED') OR
            (NEW.from_state='SUBMITTED' AND NEW.to_state='VERIFIED') OR
            (NEW.from_state='VERIFIED' AND NEW.to_state='CLOSED') OR
            (NEW.from_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')
             AND NEW.to_state='CANCELLED')) THEN
      RAISE EXCEPTION 'Handover Action state event is invalid';
    END IF;
    RETURN NEW;
  END IF;

  SELECT * INTO action_row FROM plm.hnd_action_items
   WHERE action_item_id=NEW.action_item_id FOR SHARE;
  IF action_row.action_item_id IS NULL OR NEW.project_id<>action_row.project_id THEN
    RAISE EXCEPTION 'Handover Action owned reference scope is invalid';
  END IF;
  IF TG_TABLE_NAME='hnd_action_response_refs' THEN
    IF TG_OP<>'INSERT' OR action_row.action_state<>'IN_PROGRESS' THEN
      RAISE EXCEPTION 'Handover Action response reference is immutable';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_action_evidence_refs' THEN
    IF TG_OP<>'INSERT' OR NOT (
         (NEW.purpose='SUBMISSION' AND action_row.action_state='IN_PROGRESS') OR
         (NEW.purpose='VERIFICATION' AND action_row.action_state='SUBMITTED') OR
         (NEW.purpose='RESOLUTION' AND action_row.action_state='VERIFIED')) THEN
      RAISE EXCEPTION 'Handover Action evidence reference is immutable';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_handover_action_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_action uuid;
  action_row plm.hnd_action_items%ROWTYPE;
  first_event plm.hnd_action_state_events%ROWTYPE;
  latest_event plm.hnd_action_state_events%ROWTYPE;
  event_count bigint;
  submitted_event plm.hnd_action_state_events%ROWTYPE;
  verified_event plm.hnd_action_state_events%ROWTYPE;
BEGIN
  target_action := NEW.action_item_id;
  SELECT * INTO action_row FROM plm.hnd_action_items
   WHERE action_item_id=target_action;
  IF action_row.action_item_id IS NULL THEN
    RAISE EXCEPTION 'Handover Action is missing';
  END IF;
  SELECT count(*) INTO event_count FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action;
  SELECT * INTO first_event FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action AND sequence_no=0;
  SELECT * INTO latest_event FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action ORDER BY sequence_no DESC LIMIT 1;
  IF first_event.action_state_event_id IS NULL
     OR event_count<>action_row.lock_version+1
     OR latest_event.sequence_no<>action_row.lock_version
     OR first_event.project_id<>action_row.project_id
     OR first_event.from_state IS NOT NULL OR first_event.to_state<>'OPEN'
     OR first_event.actor_id<>action_row.created_by
     OR first_event.reason<>action_row.created_reason
     OR first_event.occurred_at<action_row.created_at
     OR latest_event.project_id<>action_row.project_id
     OR latest_event.to_state<>action_row.action_state THEN
    RAISE EXCEPTION 'Handover Action state history is incomplete';
  END IF;
  IF action_row.lock_version=0 THEN
    IF action_row.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Handover Action projection does not match history';
    END IF;
  ELSIF latest_event.actor_id<>action_row.updated_by
        OR latest_event.occurred_at<>action_row.updated_at THEN
    RAISE EXCEPTION 'Handover Action projection does not match history';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_action_state_events current_event
       LEFT JOIN plm.hnd_action_state_events prior_event
         ON prior_event.action_item_id=current_event.action_item_id
        AND prior_event.sequence_no=current_event.sequence_no-1
       WHERE current_event.action_item_id=target_action
         AND current_event.sequence_no>0
         AND (prior_event.action_state_event_id IS NULL
              OR current_event.from_state<>prior_event.to_state)) THEN
    RAISE EXCEPTION 'Handover Action state history is incomplete';
  END IF;
  SELECT * INTO submitted_event FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action AND to_state='SUBMITTED';
  SELECT * INTO verified_event FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action AND to_state='VERIFIED';
  IF submitted_event.action_state_event_id IS NULL THEN
    IF action_row.submitted_at IS NOT NULL
       OR EXISTS (SELECT 1 FROM plm.hnd_action_response_refs WHERE action_item_id=target_action)
       OR EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs WHERE action_item_id=target_action) THEN
      RAISE EXCEPTION 'Handover Action submission is incomplete';
    END IF;
  ELSIF action_row.submitted_at<>submitted_event.occurred_at
        OR NOT EXISTS (SELECT 1 FROM plm.hnd_action_response_refs
                        WHERE action_item_id=target_action)
        OR NOT EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs
                        WHERE action_item_id=target_action AND purpose='SUBMISSION') THEN
    RAISE EXCEPTION 'Handover Action submission is incomplete';
  END IF;
  IF verified_event.action_state_event_id IS NULL THEN
    IF action_row.verified_by IS NOT NULL OR action_row.verified_at IS NOT NULL
       OR EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs
                   WHERE action_item_id=target_action AND purpose IN ('VERIFICATION','RESOLUTION')) THEN
      RAISE EXCEPTION 'Handover Action verification is incomplete';
    END IF;
  ELSIF action_row.verified_by<>verified_event.actor_id
        OR action_row.verified_at<>verified_event.occurred_at
        OR NOT EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs
                        WHERE action_item_id=target_action AND purpose='VERIFICATION') THEN
    RAISE EXCEPTION 'Handover Action verification is incomplete';
  END IF;
  IF action_row.action_state='CLOSED' THEN
    IF action_row.closed_at<>latest_event.occurred_at
       OR action_row.resolution_trace_ref IS NULL
       OR NOT EXISTS (
         SELECT 1 FROM plm.trc_links link
          WHERE link.trace_link_id=action_row.resolution_trace_ref
            AND link.scope='PROJECT' AND link.project_id=action_row.project_id
            AND link.target_project_id=action_row.project_id
            AND link.link_state='ACTIVE') THEN
      RAISE EXCEPTION 'Handover Action closure is incomplete';
    END IF;
  ELSIF action_row.closed_at IS NOT NULL OR action_row.resolution_trace_ref IS NOT NULL THEN
    RAISE EXCEPTION 'Handover Action closure is incomplete';
  END IF;
  IF action_row.due_at<action_row.created_at THEN
    RAISE EXCEPTION 'Handover Action due time precedes creation';
  END IF;
  IF action_row.source_kind='ANALYSIS_ITEM' THEN
    IF NOT EXISTS (
         SELECT 1 FROM plm.hnd_analysis_items item
          WHERE item.handover_analysis_version_id=action_row.source_analysis_version_ref
            AND item.analysis_item_id=action_row.source_item_id
            AND item.project_id=action_row.project_id) THEN
      RAISE EXCEPTION 'Handover Action source item is missing';
    END IF;
    IF action_row.lock_version=0 AND NOT EXISTS (
         SELECT 1 FROM plm.hnd_analysis_items item
         JOIN plm.hnd_analysis_versions version
           ON version.handover_analysis_version_id=item.handover_analysis_version_id
          WHERE item.handover_analysis_version_id=action_row.source_analysis_version_ref
            AND item.analysis_item_id=action_row.source_item_id
            AND item.project_id=action_row.project_id
            AND ((version.version_state='DRAFT' AND item.item_state='CANDIDATE')
                 OR (version.version_state='APPROVED' AND item.item_state='CONFIRMED'))) THEN
      RAISE EXCEPTION 'Handover Action source item is not eligible';
    END IF;
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_action_response_refs response
       JOIN plm.doc_document_versions version
         ON version.document_version_id=response.document_version_id
        AND version.document_id=response.document_id
       WHERE response.action_item_id=target_action
         AND (response.project_id<>action_row.project_id
              OR version.scope<>'PROJECT' OR version.project_id<>action_row.project_id
              OR version.availability_state<>'AVAILABLE'))
     OR EXISTS (
       SELECT 1 FROM plm.hnd_action_evidence_refs action_evidence
       JOIN plm.evd_evidence_records evidence
         ON evidence.evidence_id=action_evidence.evidence_id
       WHERE action_evidence.action_item_id=target_action
         AND (action_evidence.project_id<>action_row.project_id
              OR evidence.scope<>'PROJECT' OR evidence.project_id<>action_row.project_id
              OR evidence.eligibility_state<>'ELIGIBLE')) THEN
    RAISE EXCEPTION 'Handover Action owned reference is unavailable';
  END IF;
  RETURN NULL;
END; $$;
"""


def _drop_complete_triggers() -> None:
    for table in _TABLES:
        op.execute(sa.text(
            f"DROP TRIGGER IF EXISTS trg_{table}__complete ON plm.{table}"
        ))


def _create_complete_triggers(*, lifecycle: bool) -> None:
    action_events = "INSERT OR UPDATE" if lifecycle else "INSERT"
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_hnd_action_items__complete "
        f"AFTER {action_events} ON plm.hnd_action_items DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.validate_handover_action_foundation()"
    ))
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_hnd_action_state_events__complete "
        "AFTER INSERT ON plm.hnd_action_state_events DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.validate_handover_action_foundation()"
    ))
    if lifecycle:
        for table in ("hnd_action_response_refs", "hnd_action_evidence_refs"):
            op.execute(sa.text(
                f"CREATE CONSTRAINT TRIGGER trg_{table}__complete AFTER INSERT ON plm.{table} "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
                "plm.validate_handover_action_foundation()"
            ))


def upgrade() -> None:
    _drop_complete_triggers()
    op.execute(_GUARDS)
    _create_complete_triggers(lifecycle=True)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover Action lifecycle downgrade is disabled")
    op.execute("LOCK TABLE " + ", ".join("plm." + table for table in _TABLES)
               + " IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.hnd_action_items
                      WHERE action_state<>'OPEN' OR lock_version<>0)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_response_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_state_events WHERE sequence_no>0) THEN
            RAISE EXCEPTION 'Handover Action lifecycle history prevents downgrade';
          END IF;
        END $$;
    """)
    _drop_complete_triggers()
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261005_0098_handover_action_foundation"
    )
    op.execute(previous._GUARDS)
    _create_complete_triggers(lifecycle=False)
