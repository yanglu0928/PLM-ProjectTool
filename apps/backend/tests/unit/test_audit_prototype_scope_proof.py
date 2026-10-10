"""Prototype NOT_REQUIRED Audit witness fails closed on absent/ambiguous action."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row

import plm_assistant.modules.audit.infrastructure.prototype_scope_proof as module
from plm_assistant.modules.audit.application.prototype_scope_proof import (
    PrototypeScopeDecisionAuditProof,
)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self.rows


class _Session:
    def __init__(self, rows):
        self.rows = rows

    def in_transaction(self):
        return True

    def execute(self, _statement):
        return _Result(self.rows)


def _prove(monkeypatch, rows, *, decided_at=None):
    monkeypatch.setattr(module, "Session", _Session)
    project, prototype, actor = (uuid.uuid4() for _ in range(3))
    when = decided_at or datetime(2026, 10, 8, tzinfo=timezone.utc)
    return module.SqlAlchemyPrototypeScopeDecisionAuditProof().prove_user_action(
        Row(session=_Session(rows)), project_id=project,
        prototype_id=prototype, confirmed_by=actor, decided_at=when,
    )


def test_unique_nearby_user_action_is_witness_not_customer_confirmation(monkeypatch):
    when = datetime(2026, 10, 8, tzinfo=timezone.utc)
    proof = _prove(monkeypatch, (Row(audit_event_id=uuid.uuid4(),
                                   occurred_at=when + timedelta(seconds=1)),),
                   decided_at=when)
    assert type(proof) is PrototypeScopeDecisionAuditProof


def test_missing_ambiguous_or_late_action_fails_closed(monkeypatch):
    when = datetime(2026, 10, 8, tzinfo=timezone.utc)
    row = Row(audit_event_id=uuid.uuid4(),
              occurred_at=when + timedelta(seconds=1))
    assert _prove(monkeypatch, (), decided_at=when) is None
    assert _prove(monkeypatch, (row, row), decided_at=when) is None
    late = Row(audit_event_id=uuid.uuid4(),
               occurred_at=when + timedelta(minutes=6))
    assert _prove(monkeypatch, (late,), decided_at=when) is None


def test_pg_local_timezone_is_normalized_without_skipping_audit(monkeypatch):
    local = timezone(timedelta(hours=8))
    decided = datetime(2026, 10, 8, 17, 42, tzinfo=local)
    row = Row(audit_event_id=uuid.uuid4(),
              occurred_at=decided + timedelta(seconds=1))
    proof = _prove(monkeypatch, (row,), decided_at=decided)
    assert type(proof) is PrototypeScopeDecisionAuditProof
    assert proof.occurred_at.utcoffset() == timedelta(0)
    assert proof.occurred_at == datetime(2026, 10, 8, 9, 42, 1,
                                        tzinfo=timezone.utc)
    assert _prove(monkeypatch, (row,), decided_at=decided.replace(tzinfo=None)) is None
    early = Row(audit_event_id=uuid.uuid4(),
                occurred_at=decided - timedelta(seconds=1))
    assert _prove(monkeypatch, (early,), decided_at=decided) is None
    naive = Row(audit_event_id=uuid.uuid4(),
                occurred_at=decided.replace(tzinfo=None))
    assert _prove(monkeypatch, (naive,), decided_at=decided) is None
