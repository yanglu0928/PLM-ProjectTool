"""Authorized first-observation Outline validation and durable replay contract."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineRequirementRef,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OPERATION, OutlineVersionValidationFacts, ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.read_outline import OutlineCurrentView
from plm_assistant.modules.solution.application.validate_outline_version import (
    OutlineVersionValidationAudit,
    OutlineVersionValidationError,
    OutlineVersionValidationService,
)


PROJECT, OUTLINE, VERSION, SECTION, ACTOR = (uuid.uuid4() for _ in range(5))
NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
ROOT = OutlineCurrentView(
    OUTLINE, PROJECT, "Implementation solution", "ACTIVE", None,
    ACTOR, NOW, '"v0"',
)
VERSION_VIEW = OutlineVersionHistoryView(
    VERSION, OUTLINE, PROJECT, 1, "DRAFT", b"o" * 32,
    (SECTION,), (OutlineRequirementRef(uuid.uuid4(), uuid.uuid4()),),
    (), (), (), None, None, None, ACTOR, NOW,
)


class Tx:
    committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class Harness:
    def __init__(self, *, role="PROJECT_MANAGER"):
        self.role = role
        self.project_state = "ACTIVE"
        self.actor = ACTOR
        self.root = ROOT
        self.version = VERSION_VIEW
        self.current_facts = OutlineVersionValidationFacts("PASS", "PASS", "PASS")
        self.license_ok = True
        self.audit_fail = False
        self.audit_events = {}
        self.receipts = {}
        self.request_fingerprints = {}
        self.current_calls = 0
        self.txs = []
        self.authorization = ProjectAuthorizationService(
            unit_of_work=self.transaction, repository=self,
        )
        self.service = OutlineVersionValidationService(
            unit_of_work=self.transaction, access=self,
            license_guard=self, authorization=self.authorization,
            outlines=self, versions=self,
            current=SimpleNamespace(facts=self.prove_facts),
            receipts=self, audit=self,
            audit_source=SimpleNamespace(get=self.get_audit),
            clock=lambda: NOW,
        )

    def transaction(self):
        tx = Tx()
        self.txs.append(tx)
        return tx

    def authenticated_user(self, _tx, **_kwargs): return self.actor
    def require_valid(self, **_kwargs):
        if not self.license_ok:
            raise RuntimeLicenseError("EXPIRED")
    def actor_facts(self, _tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts(self.project_state, self.role)
    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("Outline validate policy has no target")
    def get_current(self, _tx, *, project_id, outline_id):
        assert project_id == PROJECT
        return self.root if outline_id == OUTLINE else None
    def get(self, _tx, *, project_id, outline_id, version_id):
        assert project_id == PROJECT and outline_id == OUTLINE
        return self.version if version_id == VERSION else None
    def prove_facts(self, _tx, *, command, version):
        assert version is self.version and command.project_id == PROJECT
        self.current_calls += 1
        return self.current_facts
    def reserve(self, _tx, *, scope, request_fingerprint):
        existing = self.receipts.get(scope.key_digest)
        if existing is not None and self.request_fingerprints[scope.key_digest] != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.request_fingerprints[scope.key_digest] = request_fingerprint
        return existing
    def complete(self, _tx, *, scope, result):
        self.receipts[scope.key_digest] = result
    def append(self, _tx, event):
        if self.audit_fail:
            raise RuntimeError("audit unavailable")
        event_id = uuid.uuid4()
        self.audit_events[event_id] = OutlineVersionValidationAudit(
            event_id, event.trace_id, NOW, event.reason_code, event.before_state,
        )
        return event_id
    def get_audit(self, _tx, *, audit_event_id, actor_id, project_id,
                  outline_id, version_id):
        assert (actor_id, project_id, outline_id, version_id) == (
            ACTOR, PROJECT, OUTLINE, VERSION,
        )
        return self.audit_events.get(audit_event_id)


def command(**changes):
    values = dict(
        session_token=b"s" * 32, csrf_token=b"c" * 32,
        trace_id=uuid.uuid4(), project_id=PROJECT,
        solution_outline_id=OUTLINE, solution_outline_version_id=VERSION,
        idempotency_key="outline-validate-0001",
    )
    values.update(changes)
    return ValidateOutlineVersion(**values)


def test_first_outline_observation_is_audited_receipted_and_not_approved():
    subject = Harness()
    first = subject.service.validate(command())
    assert first.valid and first.ready_for_review
    assert first.facts == OutlineVersionValidationFacts("PASS", "PASS", "PASS")
    assert subject.txs[-1].committed
    assert subject.current_calls == 1 and len(subject.audit_events) == 1
    assert next(iter(subject.receipts.values())) == IdempotencyResult(
        OPERATION, first.audit_event_id, 200,
    )
    assert subject.version.version_state == "DRAFT" and subject.root.current_approved_version_ref is None


def test_implementation_member_is_authorized_by_frozen_operation_policy():
    subject = Harness(role="IMPLEMENTATION_MEMBER")
    assert subject.service.validate(command()).facts.coverage == "PASS"


def test_same_key_replays_first_audit_but_new_key_reproves_current_facts():
    subject = Harness()
    first = subject.service.validate(command())
    subject.current_facts = OutlineVersionValidationFacts("PASS", "PASS", "FAIL")
    replay = subject.service.validate(command(trace_id=uuid.uuid4()))
    assert replay == first
    assert subject.current_calls == 1 and len(subject.audit_events) == 1
    assert not subject.txs[-1].committed
    changed = subject.service.validate(command(
        idempotency_key="outline-validate-0002"))
    assert changed.facts.coverage == "FAIL" and not changed.valid
    assert subject.current_calls == 2 and len(subject.audit_events) == 2


@pytest.mark.parametrize("role", ["CUSTOMER_MANAGER", "CUSTOMER_MEMBER"])
def test_customer_roles_cannot_validate_or_read_current_sources(role):
    subject = Harness(role=role)
    with pytest.raises(OutlineVersionValidationError) as caught:
        subject.service.validate(command())
    assert caught.value.code == "RESOURCE_NOT_FOUND"
    assert subject.current_calls == 0 and not subject.audit_events


def test_archived_outline_wrong_version_and_expired_license_fail_closed():
    for changed in ("project", "outline", "version", "license"):
        subject = Harness()
        if changed == "project": subject.project_state = "ARCHIVED"
        if changed == "outline": subject.root = replace(ROOT, outline_state="ARCHIVED")
        if changed == "version": subject.version = None
        if changed == "license": subject.license_ok = False
        with pytest.raises(OutlineVersionValidationError):
            subject.service.validate(command())
        assert subject.current_calls == 0 and not subject.audit_events
        assert not any(tx.committed for tx in subject.txs)


def test_audit_failure_does_not_commit_first_observation():
    subject = Harness()
    subject.audit_fail = True
    with pytest.raises(OutlineVersionValidationError):
        subject.service.validate(command())
    assert subject.current_calls == 1
    assert not subject.receipts and not subject.audit_events
    assert not subject.txs[-1].committed


def test_unknown_source_status_is_audited_as_unavailable_not_pass():
    subject = Harness()
    subject.current_facts = OutlineVersionValidationFacts("PASS", "PASS", "UNAVAILABLE")
    result = subject.service.validate(command())
    assert not result.valid and not result.ready_for_review
    assert result.issue_codes == ("REQUIREMENT_COVERAGE_UNAVAILABLE",)
