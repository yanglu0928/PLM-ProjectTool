"""Authorized SOL-06 validation orchestration and first-result replay."""

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
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    OPERATION, StructuredSpecValidationFacts,
    StructuredSpecValidationObservation, StructuredSpecValidationSnapshot,
    ValidateStructuredSpec, build_structured_spec_type_checks,
)
from plm_assistant.modules.solution.application.structured_spec_validation_source import (
    StructuredSpecValidationSource,
)
from plm_assistant.modules.solution.application.validate_structured_spec import (
    StructuredSpecValidationAudit, StructuredSpecValidationError,
    StructuredSpecValidationService,
)


PROJECT, SPEC, SERIES, ACTOR = (uuid.uuid4() for _ in range(4))
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
REQ = SpecRequirementRef(uuid.uuid4(), uuid.uuid4())
SECTION = SpecSectionRef(uuid.uuid4(), uuid.uuid4())
EVIDENCE = uuid.uuid4()
DRAFT = validate_structured_spec_draft(StructuredSpecDraftInput(
    PROJECT, None, None, "MIGRATION_SPEC", {
        "assumptions": [], "exclusions": [], "source_system": "old",
        "target_system": "new", "scope": "parts",
        "cleansing_rules": ["deduplicate"],
        "field_mappings": [{"source": "old_id", "target": "part_id"}],
        "trial_plan": "trial", "reconciliation_plan": "compare",
        "rollback_plan": "restore", "acceptance_criteria": "zero diff",
    }, (REQ,), (SECTION,), (EVIDENCE,), ()))
SNAPSHOT = StructuredSpecValidationSnapshot(
    PROJECT, SPEC, SERIES, "MIGRATION_SPEC", 1, "DRAFT",
    b"c" * 32, DRAFT.payload_fingerprint, 1, 1, 1, 0)
SOURCE = StructuredSpecValidationSource(SNAPSHOT, DRAFT, SPEC, 1)
OBSERVATION = StructuredSpecValidationObservation(
    StructuredSpecValidationFacts(
        integrity="PASS", payload="PASS", requirements="PASS",
        sections="PASS", evidence="PASS", artifacts="PASS",
        trace="UNAVAILABLE", current_version="PASS"),
    build_structured_spec_type_checks("MIGRATION_SPEC", {
        "SCOPE_MAPPING": "PASS", "TRIAL_EXECUTION": "UNAVAILABLE",
        "RECONCILIATION_PROOF": "UNAVAILABLE",
        "ROLLBACK_PROOF": "UNAVAILABLE",
        "ACCEPTANCE_PROOF": "UNAVAILABLE",
    }))


class Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.committed = True


class Harness:
    def __init__(self, role: str = "PROJECT_MANAGER") -> None:
        self.role = role
        self.project_state = "ACTIVE"
        self.actor = ACTOR
        self.license_ok = True
        self.fail_second_license = False
        self.license_calls = 0
        self.source = SOURCE
        self.observation = OBSERVATION
        self.evaluator_calls = 0
        self.repository_calls = 0
        self.audit_events: dict[uuid.UUID, StructuredSpecValidationAudit] = {}
        self.receipt = None
        self.request = None
        self.completions = 0
        self.txs: list[Tx] = []
        self.authorization = ProjectAuthorizationService(
            unit_of_work=self.transaction, repository=self)
        self.service = StructuredSpecValidationService(
            unit_of_work=self.transaction,
            access=SimpleNamespace(authenticated_user=self.authenticated_user),
            license_guard=SimpleNamespace(require_valid=self.require_valid),
            authorization=self.authorization,
            repository=SimpleNamespace(lock_source=self.lock_source),
            evaluator=SimpleNamespace(evaluate=self.evaluate),
            receipts=SimpleNamespace(reserve=self.reserve, complete=self.complete),
            audit=SimpleNamespace(append=self.append),
            audit_source=SimpleNamespace(get=self.get_audit),
            clock=lambda: NOW)

    def transaction(self):
        transaction = Tx()
        self.txs.append(transaction)
        return transaction

    def authenticated_user(self, _transaction, **_kwargs):
        return self.actor

    def require_valid(self, **_kwargs):
        self.license_calls += 1
        if not self.license_ok or (
                self.fail_second_license and self.license_calls == 2):
            raise RuntimeLicenseError("EXPIRED")

    def actor_facts(self, _transaction, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts(self.project_state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("no target")

    def lock_source(self, _transaction, *, project_id, spec_id):
        self.repository_calls += 1
        assert project_id == PROJECT
        return self.source if spec_id == SPEC else None

    def evaluate(self, _transaction, *, command, source):
        self.evaluator_calls += 1
        assert command.project_id == PROJECT and source is SOURCE
        return self.observation

    def reserve(self, _transaction, *, scope, request_fingerprint):
        if self.receipt is not None and (
                self.request != request_fingerprint
                or self.receipt[0] != scope.key_digest):
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.request = request_fingerprint
        return self.receipt[1] if self.receipt else None

    def complete(self, _transaction, *, scope, result):
        self.completions += 1
        self.receipt = (scope.key_digest, result)

    def append(self, _transaction, event):
        identity = uuid.uuid4()
        self.audit_events[identity] = StructuredSpecValidationAudit(
            identity, event.trace_id, NOW, event.reason_code,
            event.before_state)
        return identity

    def get_audit(self, _transaction, *, audit_event_id, actor_id,
                  project_id, series_id, spec_id):
        assert (actor_id, project_id, series_id, spec_id) == (
            ACTOR, PROJECT, SERIES, SPEC)
        return self.audit_events.get(audit_event_id)


def command(**changes):
    values = dict(
        session_token=b"s" * 32, csrf_token=b"c" * 32,
        trace_id=uuid.uuid4(), project_id=PROJECT,
        structured_solution_spec_id=SPEC,
        idempotency_key="structured-spec-validate-0001")
    values.update(changes)
    return ValidateStructuredSpec(**values)


def test_first_observation_is_atomic_and_does_not_mutate_spec_or_review():
    subject = Harness()
    report = subject.service.validate(command())
    assert subject.txs[-1].committed
    assert report.valid and not report.ready_for_review
    assert report.version_state == "DRAFT"
    assert "TRACE_COVERAGE_UNAVAILABLE" in report.issue_codes
    assert subject.evaluator_calls == subject.completions == 1
    assert subject.receipt[1] == IdempotencyResult(
        OPERATION, report.audit_event_id, 200)
    assert subject.source.snapshot == SNAPSHOT


def test_replay_returns_first_trace_time_and_observation_without_resampling():
    subject = Harness()
    first = subject.service.validate(command())
    subject.observation = replace(
        OBSERVATION,
        facts=replace(OBSERVATION.facts, requirements="UNAVAILABLE"))
    replay = subject.service.validate(command(trace_id=uuid.uuid4()))
    assert replay == first
    assert subject.evaluator_calls == 1
    assert subject.repository_calls == 2
    assert subject.completions == 1 and len(subject.audit_events) == 1
    assert not subject.txs[-1].committed


@pytest.mark.parametrize("role", ["CUSTOMER_MANAGER", "CUSTOMER_MEMBER"])
def test_non_writer_role_cannot_reserve_read_source_or_audit(role):
    subject = Harness(role)
    with pytest.raises(StructuredSpecValidationError) as failure:
        subject.service.validate(command())
    assert failure.value.code == "RESOURCE_NOT_FOUND"
    assert subject.request is None and subject.repository_calls == 0
    assert not subject.audit_events


def test_archived_project_missing_spec_and_cross_project_identity_fail_closed():
    archived = Harness()
    archived.project_state = "ARCHIVED"
    missing = Harness()
    missing.source = None
    for subject in (archived, missing):
        with pytest.raises(StructuredSpecValidationError):
            subject.service.validate(command())
        assert not subject.txs[-1].committed and not subject.audit_events


def test_invalid_session_and_license_stop_before_repository():
    for change in ("session", "license"):
        subject = Harness()
        if change == "session":
            subject.actor = None
        else:
            subject.license_ok = False
        with pytest.raises(StructuredSpecValidationError):
            subject.service.validate(command())
        assert subject.repository_calls == 0 and not subject.audit_events


def test_receipt_conflict_and_missing_audit_proof_do_not_commit():
    conflict = Harness()
    conflict.receipt = (
        b"r" * 32, IdempotencyResult(OPERATION, uuid.uuid4(), 200))
    conflict.request = b"r" * 32
    with pytest.raises(StructuredSpecValidationError) as failure:
        conflict.service.validate(command())
    assert failure.value.code == "CONFLICT_IDEMPOTENCY"

    missing = Harness()
    missing.service._audit_source.get = lambda *_args, **_kwargs: None
    with pytest.raises(StructuredSpecValidationError):
        missing.service.validate(command())
    assert not missing.txs[-1].committed


def test_license_recheck_failure_rolls_back_first_observation():
    subject = Harness()
    subject.fail_second_license = True
    with pytest.raises(StructuredSpecValidationError) as failure:
        subject.service.validate(command())
    assert failure.value.code == "LICENSE_OPERATION_DENIED"
    assert subject.license_calls == 2
    assert not subject.txs[-1].committed


def test_dependencies_command_and_evaluator_result_are_strict():
    subject = Harness()
    with pytest.raises(StructuredSpecValidationError) as failure:
        subject.service.validate(object())
    assert failure.value.code == "VALIDATION_FAILED"
    subject.observation = None
    with pytest.raises(StructuredSpecValidationError):
        subject.service.validate(command())
    with pytest.raises(ValueError):
        StructuredSpecValidationService(
            unit_of_work=None, access=object(), license_guard=object(),
            authorization=subject.authorization, repository=object(),
            evaluator=object(), receipts=object(), audit=object(),
            audit_source=object())
