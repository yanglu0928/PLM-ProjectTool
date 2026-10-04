"""Allow versioned Handover Action metadata changes.

Revision ID: 20261005_0100
Revises: 20261005_0099
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261005_0100"
down_revision = "20261005_0099"
branch_labels = None
depends_on = None

_previous = importlib.import_module(
    "plm_assistant.migrations.versions.20261005_0099_handover_action_lifecycle"
)


def _once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError("Handover Action metadata guard anchor changed")
    return source.replace(old, new)


_GUARDS = _once(
    _previous._GUARDS,
    """ROW(NEW.action_item_id,NEW.project_id,NEW.source_kind,
           NEW.source_analysis_version_ref,NEW.source_item_id,NEW.human_source_reason,
           NEW.action_type,NEW.title,NEW.requested_input_spec,NEW.owner_ref,NEW.due_at,
           NEW.priority,NEW.created_by,NEW.created_reason,NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.action_item_id,OLD.project_id,OLD.source_kind,
           OLD.source_analysis_version_ref,OLD.source_item_id,OLD.human_source_reason,
           OLD.action_type,OLD.title,OLD.requested_input_spec,OLD.owner_ref,OLD.due_at,
           OLD.priority,OLD.created_by,OLD.created_reason,OLD.created_at)""",
    """ROW(NEW.action_item_id,NEW.project_id,NEW.source_kind,
           NEW.source_analysis_version_ref,NEW.source_item_id,NEW.human_source_reason,
           NEW.action_type,NEW.created_by,NEW.created_reason,NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.action_item_id,OLD.project_id,OLD.source_kind,
           OLD.source_analysis_version_ref,OLD.source_item_id,OLD.human_source_reason,
           OLD.action_type,OLD.created_by,OLD.created_reason,OLD.created_at)""",
)
_GUARDS = _once(
    _GUARDS,
    """(OLD.action_state='VERIFIED' AND NEW.action_state='CLOSED') OR
      (OLD.action_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')""",
    """(OLD.action_state='VERIFIED' AND NEW.action_state='CLOSED') OR
      (OLD.action_state=NEW.action_state AND OLD.action_state IN ('OPEN','IN_PROGRESS')) OR
      (OLD.action_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')""",
)
_GUARDS = _once(
    _GUARDS,
    """IF NOT allowed_transition THEN
      RAISE EXCEPTION 'Handover Action state transition is invalid';
    END IF;""",
    """IF NOT allowed_transition THEN
      RAISE EXCEPTION 'Handover Action state transition is invalid';
    END IF;
    IF OLD.action_state=NEW.action_state AND
       ROW(NEW.title,NEW.requested_input_spec,NEW.owner_ref,NEW.due_at,NEW.priority)
       IS NOT DISTINCT FROM
       ROW(OLD.title,OLD.requested_input_spec,OLD.owner_ref,OLD.due_at,OLD.priority) THEN
      RAISE EXCEPTION 'Handover Action metadata change is empty';
    END IF;""",
)
_GUARDS = _once(
    _GUARDS,
    """(NEW.from_state='VERIFIED' AND NEW.to_state='CLOSED') OR
            (NEW.from_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')""",
    """(NEW.from_state='VERIFIED' AND NEW.to_state='CLOSED') OR
            (NEW.from_state=NEW.to_state AND NEW.from_state IN ('OPEN','IN_PROGRESS')) OR
            (NEW.from_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED')""",
)


def upgrade() -> None:
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover Action metadata downgrade is disabled")
    op.execute("LOCK TABLE plm.hnd_action_items, plm.hnd_action_state_events "
               "IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.hnd_action_state_events
                      WHERE sequence_no>0 AND from_state=to_state) THEN
            RAISE EXCEPTION 'Handover Action metadata history prevents downgrade';
          END IF;
        END $$;
    """)
    op.execute(_previous._GUARDS)
