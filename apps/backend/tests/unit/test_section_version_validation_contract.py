"""Pure contract tests; trusted current-fact Owner is a separate WBS."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from plm_assistant.modules.solution.application.section_version_validation_contract import (
    AUDIT_ACTION,
    OPERATION,
    SectionVersionValidationContractError,
    SectionVersionValidationFacts,
    SectionVersionValidationSnapshot,
    ValidateSectionVersion,
    audit_reason_for_facts,
    build_section_version_validation_report,
    facts_from_audit_reason,
)


PROJECT, SECTION, VERSION, ACTOR, TRACE, AUDIT = (uuid.uuid4() for _ in range(6))
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def command(**changes):
    values = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                  trace_id=TRACE, project_id=PROJECT, solution_section_id=SECTION,
                  solution_section_version_id=VERSION,
                  idempotency_key="section-validate-0001")
    values.update(changes)
    return ValidateSectionVersion(**values)


def snapshot(**changes):
    values = dict(project_id=PROJECT, solution_section_id=SECTION,
                  solution_section_version_id=VERSION, version_no=6,
                  version_state="DRAFT", content_fingerprint=b"f" * 32,
                  requirement_count=1, evidence_count=1)
    values.update(changes)
    return SectionVersionValidationSnapshot(**values)


def report(facts=None, fixed=None):
    return build_section_version_validation_report(
        command(), fixed or snapshot(), facts or SectionVersionValidationFacts(),
        audit_event_id=AUDIT, observed_at=NOW)


def proven():
    return SectionVersionValidationFacts(integrity="PASS", content="PASS",
                                         requirements="PASS", evidence="PASS",
                                         trace="PASS", spec="PASS")


def test_command_binds_original_key_actor_and_fixed_identity_only():
    first = command()
    assert OPERATION == "V1_SOL_SECTION_VERSION_VALIDATE"
    assert AUDIT_ACTION == "SOL_SECTION_VERSION_VALIDATED"
    assert first.request_fingerprint() == command(trace_id=uuid.uuid4(),
                                                   idempotency_key="another-original-key").request_fingerprint()
    assert first.request_fingerprint() != command(solution_section_version_id=uuid.uuid4()).request_fingerprint()
    assert first.scope(ACTOR).operation == OPERATION
    assert first.scope(ACTOR).key_digest != command(idempotency_key="different-key-0001").scope(ACTOR).key_digest
    assert "section-validate-0001" not in repr(first)
    assert "b'sssss" not in repr(first)


@pytest.mark.parametrize("changes", [
    {"session_token": b"s"}, {"csrf_token": b"c"},
    {"project_id": uuid.UUID(int=0)}, {"solution_section_id": "wrong"},
    {"solution_section_version_id": uuid.UUID(int=0)},
    {"idempotency_key": "short"}, {"idempotency_key": "x" * 129},
])
def test_command_rejects_invalid_identity_and_key(changes):
    with pytest.raises(SectionVersionValidationContractError):
        command(**changes)


def test_missing_facts_do_not_become_a_pass():
    value = report()
    assert not value.valid and not value.ready_for_review
    assert value.issue_codes == (
        "FIXED_VERSION_UNAVAILABLE", "CONTENT_SOURCE_UNAVAILABLE",
        "REQUIREMENT_SOURCE_UNAVAILABLE", "EVIDENCE_SOURCE_UNAVAILABLE",
        "TRACE_COVERAGE_UNAVAILABLE", "STRUCTURED_SPEC_UNAVAILABLE")
    assert value.audit_event_id == AUDIT and value.trace_id == TRACE
    assert value.content_fingerprint == b"f" * 32
    assert "b'ffffffff" not in repr(value)


@pytest.mark.parametrize("dimension", [
    "integrity", "content", "requirements", "evidence", "trace", "spec",
])
@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE"])
def test_any_unproven_dimension_blocks_review(dimension, status):
    value = report(replace(proven(), **{dimension: status}))
    assert not value.ready_for_review
    assert len(value.issue_codes) == 1
    assert value.issue_codes[0].endswith(status)
    assert value.valid == (dimension in ("trace", "spec"))


def test_all_proven_draft_is_review_ready_but_not_approved():
    value = report(proven())
    assert value.valid and value.ready_for_review and value.issue_codes == ()
    assert value.version_state == "DRAFT"
    assert value.version_no == 6


def test_audit_reason_round_trips_first_observation_without_live_recheck():
    facts = replace(proven(), content="FAIL", trace="UNAVAILABLE")
    reason = audit_reason_for_facts(facts)
    assert reason == "SECTION_VALIDATION_V1_PFPPUP"
    assert facts_from_audit_reason(reason) == facts
    assert facts_from_audit_reason(audit_reason_for_facts(SectionVersionValidationFacts())) == (
        SectionVersionValidationFacts())
    for corrupt in ("SECTION_VALIDATION_V1_PPPPP", "SECTION_VALIDATION_V1_PPPPPX",
                    "SURVEY_VALIDATION_PASSED", "SECTION_VALIDATION_V1_pppppp", None):
        with pytest.raises(SectionVersionValidationContractError):
            facts_from_audit_reason(corrupt)


def test_non_draft_remains_unready_even_if_all_proofs_pass():
    value = report(proven(), snapshot(version_state="IN_REVIEW"))
    assert value.valid and not value.ready_for_review
    assert value.issue_codes == ("VERSION_NOT_DRAFT",)


def test_foreign_snapshot_and_malformed_facts_fail_closed():
    with pytest.raises(SectionVersionValidationContractError):
        report(proven(), snapshot(project_id=uuid.uuid4()))
    with pytest.raises(SectionVersionValidationContractError):
        SectionVersionValidationFacts(spec="SKIPPED")
    with pytest.raises(SectionVersionValidationContractError):
        snapshot(content_fingerprint=b"bad")


def test_report_cannot_be_forged_into_a_ready_conclusion():
    value = report()
    with pytest.raises(SectionVersionValidationContractError):
        replace(value, ready_for_review=True)
    with pytest.raises(SectionVersionValidationContractError):
        replace(value, issue_codes=())
    with pytest.raises(SectionVersionValidationContractError):
        replace(value, observed_at=NOW.replace(tzinfo=None))
