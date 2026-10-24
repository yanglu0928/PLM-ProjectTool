"""Current reproof uses fixed historical identity and cannot infer coverage."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef,
    OutlineRequirementRef,
    OutlineVersionDraftInput,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.prove_outline_section_use import (
    OutlineSectionUseProof,
)
from plm_assistant.modules.solution.application.prove_outline_coverage import (
    CurrentOutlineCoverageProof,
    OutlineCoverageProofError,
)
from plm_assistant.modules.solution.application.prove_outline_version_current import (
    OutlineVersionCurrentFactsService,
    OutlineVersionCurrentProofError,
)
from plm_assistant.modules.solution.application.prove_outline_version_input import (
    CurrentOutlineVersionBase,
    OutlineVersionInputProofService,
)
from plm_assistant.modules.solution.application.prove_reference_use import (
    EligibleReferenceUseProof,
)


@pytest.fixture
def example():
    project, outline, section, version_id, trace, actor = (uuid.uuid4() for _ in range(6))
    requirement = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
    reference = OutlineReferenceRef("GLOBAL", uuid.uuid4(), uuid.uuid4())
    supersedes = uuid.uuid4()
    sections, requirements, references, bases = (Mock(), Mock(), Mock(), Mock())
    sections.prove.return_value = OutlineSectionUseProof(project, outline, section)
    requirements.prove.return_value = OutlineApprovedRequirementProof(
        project, requirement.requirement_id, requirement.requirement_version_id,
        1, b"r" * 32, uuid.uuid4(), uuid.uuid4())
    references.prove.return_value = EligibleReferenceUseProof(
        reference.reference_solution_id, reference.reference_version_id,
        "GLOBAL", project, b"g" * 32, uuid.uuid4(), uuid.uuid4())
    bases.current.return_value = CurrentOutlineVersionBase(
        project, outline, 2, supersedes, 9)
    draft = OutlineVersionDraftInput(
        project, outline, (section,), (requirement,), (reference,), (), ())
    original = OutlineVersionInputProofService(
        bases=bases, sections=sections,
        requirements=requirements, references=references).prove(
            object(), trace_id=trace, draft=draft)
    history = OutlineVersionHistoryView(
        version_id, outline, project, 2, "DRAFT", original.content_fingerprint,
        draft.section_ids, draft.requirement_refs, draft.reference_refs,
        draft.missing_declarations, draft.conflict_declarations,
        supersedes, None, None, actor,
        datetime(2026, 10, 23, tzinfo=timezone.utc))
    command = ValidateOutlineVersion(
        b"s" * 32, b"c" * 32, trace, project, outline, version_id,
        "outline-current-0001")
    current = OutlineVersionCurrentFactsService(
        sections=sections, requirements=requirements, references=references)
    for port in (sections, requirements, references, bases):
        port.reset_mock()
    return dict(tx=object(), command=command, history=history,
                current=current, sections=sections, requirements=requirements,
                references=references, bases=bases, requirement=requirement,
                reference=reference)


def facts(example, **version_changes):
    return example["current"].facts(
        example["tx"], command=example["command"],
        version=replace(example["history"], **version_changes))


def test_current_fixed_sources_match_historical_fingerprint_but_not_coverage(example):
    result = facts(example)
    assert (result.order, result.source, result.coverage) == (
        "PASS", "PASS", "UNAVAILABLE")
    example["bases"].current.assert_not_called()
    example["sections"].prove.assert_called_once_with(
        example["tx"], project_id=example["command"].project_id,
        outline_id=example["command"].solution_outline_id,
        section_id=example["history"].section_ids[0])


def test_current_coverage_requires_exact_proof_after_fixed_sources_pass(example):
    history = example["history"]
    coverage = Mock()
    coverage.prove.return_value = CurrentOutlineCoverageProof(
        history.project_id, history.solution_outline_id,
        history.solution_outline_version_id, history.requirement_refs,
        (uuid.uuid4(),), b"i" * 32,
    )
    example["current"]._coverage = coverage
    result = facts(example)
    assert (result.order, result.source, result.coverage) == (
        "PASS", "PASS", "PASS")
    coverage.prove.assert_called_once_with(
        example["tx"], command=example["command"], version=history)
    coverage.prove.return_value = replace(coverage.prove.return_value,
                                          requirement_refs=())
    assert facts(example).coverage == "UNAVAILABLE"


def test_current_coverage_known_gap_fails_but_unknown_or_stale_source_does_not_pass(example):
    coverage = Mock()
    example["current"]._coverage = coverage
    coverage.prove.side_effect = OutlineCoverageProofError(
        "SOLUTION_COVERAGE_INCOMPLETE")
    assert facts(example).coverage == "FAIL"
    coverage.prove.side_effect = OutlineCoverageProofError()
    assert facts(example).coverage == "UNAVAILABLE"
    coverage.prove.reset_mock()
    example["requirements"].prove.side_effect = RuntimeError("source unavailable")
    assert facts(example).coverage == "UNAVAILABLE"
    coverage.prove.assert_not_called()


def test_newer_dynamic_next_version_does_not_change_old_version_proof(example):
    example["bases"].current.return_value = CurrentOutlineVersionBase(
        example["command"].project_id,
        example["command"].solution_outline_id, 99, uuid.uuid4(), 99)
    assert facts(example).source == "PASS"
    example["bases"].current.assert_not_called()


def test_current_reference_drift_fails_full_source_fingerprint(example):
    proof = example["references"].prove.return_value
    example["references"].prove.return_value = replace(
        proof, source_fingerprint=b"x" * 32)
    assert (facts(example).order, facts(example).source) == ("PASS", "FAIL")


def test_current_requirement_drift_fails_full_source_fingerprint(example):
    proof = example["requirements"].prove.return_value
    example["requirements"].prove.return_value = replace(
        proof, review_round_id=uuid.uuid4())
    assert facts(example).source == "FAIL"


@pytest.mark.parametrize("failed_port", ["sections", "requirements", "references"])
def test_missing_or_broken_current_source_is_unavailable(example, failed_port):
    example[failed_port].prove.side_effect = RuntimeError("private source failure")
    result = facts(example)
    assert result.order == "PASS" and result.source == "UNAVAILABLE"
    assert result.coverage == "UNAVAILABLE"


def test_invalid_historical_order_fails_without_current_source_calls(example):
    result = facts(example, section_ids=(example["history"].section_ids[0],) * 2)
    assert result.order == "FAIL" and result.source == "UNAVAILABLE"
    example["sections"].prove.assert_not_called()


def test_invalid_fixed_identity_or_fingerprint_fails_closed(example):
    with pytest.raises(OutlineVersionCurrentProofError):
        facts(example, content_fingerprint=b"bad")
    with pytest.raises(OutlineVersionCurrentProofError):
        facts(example, project_id=uuid.uuid4())
    with pytest.raises(OutlineVersionCurrentProofError):
        example["current"].facts(None, command=example["command"],
                                 version=example["history"])


def test_no_ports_are_optional():
    with pytest.raises(ValueError):
        OutlineVersionCurrentFactsService(
            sections=Mock(), requirements=None, references=Mock())
