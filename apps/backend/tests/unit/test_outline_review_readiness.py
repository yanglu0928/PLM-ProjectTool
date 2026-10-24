"""Outline Review re-proves the latest fixed version in the caller transaction."""

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from plm_assistant.modules.solution.application.outline_review_readiness import (
    OutlineReviewReadinessError, OutlineReviewReadinessService,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery, OutlineVersionValidationFacts,
)


PROJECT, OUTLINE, VERSION, ACTOR, TRACE = (uuid4() for _ in range(5))
NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
FIXED = OutlineVersionHistoryView(
    VERSION, OUTLINE, PROJECT, 1, "DRAFT", b"x" * 32, (uuid4(),),
    (), (), (), (), None, None, None, ACTOR, NOW)
QUERY = OutlineCurrentFactQuery(b"s" * 32, TRACE, PROJECT, OUTLINE, VERSION)


class Harness:
    def __init__(self):
        self.version = FIXED
        self.facts = OutlineVersionValidationFacts("PASS", "PASS", "PASS")
        self.calls = []
        self.service = OutlineReviewReadinessService(
            repository=SimpleNamespace(lock_latest=self.lock_latest),
            current=SimpleNamespace(facts=self.current_facts), clock=lambda: NOW)

    def lock_latest(self, transaction, **identity):
        self.calls.append(("lock", transaction, identity))
        return self.version

    def current_facts(self, transaction, *, command, version):
        self.calls.append(("facts", transaction, command, version))
        return self.facts


@pytest.mark.parametrize("state", ["DRAFT", "IN_REVIEW"])
def test_exact_latest_current_three_dimension_proof(state):
    harness, tx = Harness(), object()
    harness.version = replace(FIXED, version_state=state)
    proof = harness.service.prove(tx, query=QUERY, required_state=state)
    assert proof.version == harness.version
    assert proof.content_fingerprint == FIXED.content_fingerprint
    assert harness.calls == [
        ("lock", tx, dict(project_id=PROJECT, outline_id=OUTLINE,
                          version_id=VERSION, required_state=state)),
        ("facts", tx, QUERY, harness.version),
    ]


@pytest.mark.parametrize("dimension", ["order", "source", "coverage"])
@pytest.mark.parametrize("value", ["FAIL", "UNAVAILABLE"])
def test_any_non_pass_fact_fails_closed(dimension, value):
    harness = Harness()
    harness.facts = replace(harness.facts, **{dimension: value})
    with pytest.raises(OutlineReviewReadinessError):
        harness.service.prove(object(), query=QUERY)


@pytest.mark.parametrize("version", [
    None, replace(FIXED, version_state="APPROVED"),
    replace(FIXED, solution_outline_version_id=uuid4()),
    replace(FIXED, project_id=uuid4()),
    replace(FIXED, content_fingerprint=b"bad"),
])
def test_missing_stale_or_mismatched_source_never_reads_facts(version):
    harness = Harness()
    harness.version = version
    with pytest.raises(OutlineReviewReadinessError):
        harness.service.prove(object(), query=QUERY)
    assert not any(call[0] == "facts" for call in harness.calls)


def test_terminal_requires_in_review_and_valid_call_context():
    harness = Harness()
    with pytest.raises(OutlineReviewReadinessError):
        harness.service.prove(object(), query=QUERY, required_state="IN_REVIEW")
    with pytest.raises(OutlineReviewReadinessError):
        harness.service.prove(None, query=QUERY)
    with pytest.raises(OutlineReviewReadinessError):
        harness.service.prove(object(), query=QUERY, required_state="APPROVED")
