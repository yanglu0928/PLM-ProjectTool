"""Owner orchestration tests; PG source and audit integration is separate."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError, IdempotencyResult
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineApprovedRequirementProof
from plm_assistant.modules.solution.application.prove_section_document_content import SectionDocumentContentProof
from plm_assistant.modules.solution.application.prove_section_evidence_use import SectionEvidenceUseProof
from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from plm_assistant.modules.solution.application.read_section_version import SectionVersionHistoryView
from plm_assistant.modules.solution.application.section_version_input import SectionRequirementRef
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    OPERATION, ValidateSectionVersion,
)
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionCurrentValidator, SectionVersionValidationAudit,
    SectionVersionValidationError, SectionVersionValidationService,
)
from plm_assistant.modules.trace.application.implements_coverage import (
    TraceImplementsCoverageError, TraceImplementsCoverageProof,
)
from plm_assistant.modules.trace.application.target_proof import TraceProofQuery
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


PROJECT, SECTION, OUTLINE, VERSION, DOCUMENT, DOC_VERSION, REQUIREMENT, REQ_VERSION, EVIDENCE, ACTOR = (
    uuid.uuid4() for _ in range(10))
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
ROOT = SectionCurrentView(SECTION, OUTLINE, PROJECT, "Body", "ACTIVE", None, ACTOR, NOW, '"v0"')
VERSION_VIEW = SectionVersionHistoryView(
    VERSION, SECTION, PROJECT, 1, "DRAFT", "Body", DOC_VERSION, None,
    b"f" * 32, (SectionRequirementRef(REQUIREMENT, REQ_VERSION),), (EVIDENCE,),
    (), (), None, None, None, ACTOR, NOW)


class Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class FakeSources:
    document_ok = True
    requirement_ok = True
    evidence_ok = True
    def document(self, _tx, **_kwargs):
        if not self.document_ok: raise RuntimeError("source unavailable")
        return SectionDocumentContentProof(PROJECT, DOCUMENT, DOC_VERSION, b"d" * 32)
    def requirement(self, _tx, **_kwargs):
        if not self.requirement_ok: raise RuntimeError("source unavailable")
        return OutlineApprovedRequirementProof(PROJECT, REQUIREMENT, REQ_VERSION, 1,
                                               b"r" * 32, uuid.uuid4(), uuid.uuid4())
    def proof(self, _tx, **_kwargs):
        if not self.evidence_ok: raise RuntimeError("source unavailable")
        return SectionEvidenceUseProof(EVIDENCE, PROJECT, DOCUMENT, DOC_VERSION, 0, b"e" * 32)


class Harness:
    def __init__(self, role="PROJECT_MANAGER"):
        self.role = role; self.project_state = "ACTIVE"; self.actor = ACTOR
        self.root = ROOT; self.version = VERSION_VIEW; self.license_ok = True
        self.audit_events = {}; self.receipt = None; self.request = None
        self.source_calls = 0; self.completions = 0; self.txs = []
        self.sources = FakeSources()
        self.authorization = ProjectAuthorizationService(
            unit_of_work=self.transaction, repository=self)
        self.current = SectionVersionCurrentValidator(
            documents=SimpleNamespace(prove=self.document),
            requirements=SimpleNamespace(prove=self.requirement),
            evidence=SimpleNamespace(prove=self.evidence))
        self.service = SectionVersionValidationService(
            unit_of_work=self.transaction,
            access=SimpleNamespace(authenticated_user=self.authenticated_user),
            license_guard=SimpleNamespace(require_valid=self.require_valid),
            authorization=self.authorization,
            sections=SimpleNamespace(get_current=self.get_current),
            versions=SimpleNamespace(get=self.get), current=self.current,
            receipts=SimpleNamespace(reserve=self.reserve, complete=self.complete),
            audit=SimpleNamespace(append=self.append),
            audit_source=SimpleNamespace(get=self.get_audit),
            clock=lambda: NOW)

    def transaction(self):
        tx = Tx(); self.txs.append(tx); return tx
    def authenticated_user(self, _tx, **_kwargs): return self.actor
    def require_valid(self, **_kwargs):
        if not self.license_ok: raise RuntimeLicenseError("EXPIRED")
    def actor_facts(self, _tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts(self.project_state, self.role)
    def owner_project_id(self, *_args, **_kwargs): raise AssertionError("no target")
    def get_current(self, _tx, *, project_id, section_id):
        assert project_id == PROJECT
        return self.root if section_id == SECTION else None
    def get(self, _tx, *, project_id, section_id, version_id):
        assert project_id == PROJECT and section_id == SECTION
        return self.version if version_id == VERSION else None
    def document(self, *args, **kwargs):
        self.source_calls += 1; return self.sources.document(*args, **kwargs)
    def requirement(self, *args, **kwargs):
        self.source_calls += 1; return self.sources.requirement(*args, **kwargs)
    def evidence(self, *args, **kwargs):
        self.source_calls += 1; return self.sources.proof(*args, **kwargs)
    def reserve(self, _tx, *, scope, request_fingerprint):
        if self.receipt is not None and (self.request != request_fingerprint
                                         or self.receipt[0] != scope.key_digest):
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.request = request_fingerprint
        return self.receipt[1] if self.receipt else None
    def complete(self, _tx, *, scope, result):
        self.completions += 1
        self.receipt = (scope.key_digest, result)
    def append(self, _tx, event):
        identity = uuid.uuid4()
        self.audit_events[identity] = SectionVersionValidationAudit(
            identity, event.trace_id, NOW, event.reason_code, event.before_state)
        return identity
    def get_audit(self, _tx, *, audit_event_id, actor_id, project_id, section_id, version_id):
        assert (actor_id, project_id, section_id, version_id) == (ACTOR, PROJECT, SECTION, VERSION)
        return self.audit_events.get(audit_event_id)


def command(**changes):
    fields = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                  trace_id=uuid.uuid4(), project_id=PROJECT,
                  solution_section_id=SECTION,
                  solution_section_version_id=VERSION,
                  idempotency_key="section-validate-0001")
    fields.update(changes)
    return ValidateSectionVersion(**fields)


def test_first_owner_observation_is_audited_and_receipted_without_review_mutation():
    subject = Harness()
    report = subject.service.validate(command())
    assert subject.txs[-1].committed
    assert report.valid and not report.ready_for_review
    assert report.issue_codes == ("TRACE_COVERAGE_UNAVAILABLE", "STRUCTURED_SPEC_UNAVAILABLE")
    assert subject.source_calls == 3 and subject.completions == 1
    assert subject.receipt[1] == IdempotencyResult(OPERATION, report.audit_event_id, 200)
    assert subject.version.version_state == "DRAFT"


def test_replay_returns_original_audit_not_current_sources_or_new_trace():
    subject = Harness()
    first = subject.service.validate(command())
    subject.sources.document_ok = False
    replay = subject.service.validate(command(trace_id=uuid.uuid4()))
    assert replay == first
    assert subject.source_calls == 3
    assert subject.completions == 1 and len(subject.audit_events) == 1
    assert not subject.txs[-1].committed


@pytest.mark.parametrize("role", ["CUSTOMER_MANAGER", "CUSTOMER_MEMBER"])
def test_non_writer_role_has_no_source_or_audit_access(role):
    subject = Harness(role)
    with pytest.raises(SectionVersionValidationError) as found:
        subject.service.validate(command())
    assert found.value.code == "RESOURCE_NOT_FOUND"
    assert not subject.audit_events and not subject.source_calls


def test_archived_project_or_section_and_wrong_version_fail_closed():
    for change in ("project", "section", "version"):
        subject = Harness()
        if change == "project": subject.project_state = "ARCHIVED"
        if change == "section": subject.root = replace(ROOT, section_state="ARCHIVED")
        if change == "version": subject.version = None
        with pytest.raises(SectionVersionValidationError):
            subject.service.validate(command())
        assert not subject.audit_events and not subject.txs[-1].committed


def test_expired_license_and_invalid_session_stop_before_source_read():
    for change in ("license", "session"):
        subject = Harness()
        if change == "license": subject.license_ok = False
        if change == "session": subject.actor = None
        with pytest.raises(SectionVersionValidationError):
            subject.service.validate(command())
        assert subject.source_calls == 0 and not subject.audit_events


def test_source_failures_are_unavailable_not_a_false_pass():
    subject = Harness()
    subject.sources.document_ok = False
    subject.sources.requirement_ok = False
    subject.sources.evidence_ok = False
    report = subject.service.validate(command())
    assert not report.valid and not report.ready_for_review
    assert report.facts.content == "UNAVAILABLE"
    assert report.facts.requirements == "UNAVAILABLE"
    assert report.facts.evidence == "UNAVAILABLE"
    assert report.issue_codes[0] == "CONTENT_SOURCE_UNAVAILABLE"


def test_exact_current_trace_proof_is_audited_but_spec_still_blocks_review():
    subject = Harness()
    link_id = uuid.uuid4()
    seen = []
    def prove(tx, *, query, target, requirement_refs):
        seen.append((tx, query, target, requirement_refs))
        return TraceImplementsCoverageProof(target, requirement_refs, (link_id,))
    subject.current._trace = SimpleNamespace(prove=prove)
    cmd = command()
    report = subject.service.validate(cmd)
    assert report.facts.trace == "PASS"
    assert report.facts.spec == "UNAVAILABLE"
    assert report.valid and not report.ready_for_review
    assert report.issue_codes == ("STRUCTURED_SPEC_UNAVAILABLE",)
    assert len(seen) == 1 and seen[0][0] is subject.txs[-1]
    assert seen[0][1] == TraceProofQuery(cmd.session_token, cmd.trace_id)
    assert seen[0][2] == TraceVersionRef(
        "solution", "SOL-05", SECTION, VERSION, "PROJECT", PROJECT)
    assert seen[0][3] == (TraceVersionRef(
        "requirement", "REQ-03", REQUIREMENT, REQ_VERSION,
        "PROJECT", PROJECT),)


@pytest.mark.parametrize("failure,expected", [
    ("missing", "FAIL"), ("unavailable", "UNAVAILABLE"),
    ("wrong_target", "UNAVAILABLE"), ("wrong_count", "UNAVAILABLE"),
])
def test_trace_missing_or_malformed_never_becomes_pass(failure, expected):
    subject = Harness()
    def prove(_tx, *, query, target, requirement_refs):
        if failure == "missing":
            raise TraceImplementsCoverageError()
        if failure == "unavailable":
            raise TraceImplementsCoverageError("TRACE_UNAVAILABLE")
        if failure == "wrong_target":
            return TraceImplementsCoverageProof(
                replace(target, version_id=uuid.uuid4()),
                requirement_refs, (uuid.uuid4(),))
        return TraceImplementsCoverageProof(
            target, requirement_refs, (uuid.uuid4(), uuid.uuid4()))
    subject.current._trace = SimpleNamespace(prove=prove)
    report = subject.service.validate(command())
    assert report.facts.trace == expected
    assert not report.ready_for_review
    assert f"TRACE_COVERAGE_{expected}" in report.issue_codes


def test_missing_audit_proof_or_receipt_conflict_does_not_commit():
    subject = Harness()
    subject.service._audit_source.get = lambda *_a, **_k: None
    with pytest.raises(SectionVersionValidationError):
        subject.service.validate(command())
    assert not subject.txs[-1].committed
    another = Harness()
    another.receipt = (b"r" * 32, IdempotencyResult(OPERATION, uuid.uuid4(), 200))
    another.request = b"r" * 32
    with pytest.raises(SectionVersionValidationError) as found:
        another.service.validate(command())
    assert found.value.code == "CONFLICT_IDEMPOTENCY"
    assert not another.audit_events
