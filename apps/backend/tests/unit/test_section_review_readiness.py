"""Section Review pre-submit current proof is separate from VALIDATE history."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_review_readiness import (
    SectionReviewReadinessError, SectionReviewReadinessService,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    SectionCurrentFactQuery, SectionVersionValidationFacts,
)


PROJECT, SECTION, VERSION, ACTOR = (uuid.uuid4() for _ in range(4))
NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)
FIXED = SectionVersionHistoryView(
    VERSION, SECTION, PROJECT, 1, "DRAFT", "Body", uuid.uuid4(), None,
    b"x" * 32, (), (), (), (), None, None, None, ACTOR, NOW,
    "NONE_REQUIRED", "No structured spec applies", ())
FACTS = SectionVersionValidationFacts(*(["PASS"] * 6))
QUERY = SectionCurrentFactQuery(b"s" * 32, uuid.uuid4(), PROJECT, SECTION, VERSION)


class Harness:
    def __init__(self):
        self.version = FIXED
        self.facts = FACTS
        self.calls = []
        self.service = SectionReviewReadinessService(
            repository=SimpleNamespace(lock_latest=self.lock_latest),
            current=SimpleNamespace(facts=self.current_facts), clock=lambda: NOW)

    def lock_latest(self, transaction, **identity):
        self.calls.append(("lock", transaction, identity))
        return self.version

    def current_facts(self, transaction, *, command, version):
        self.calls.append(("facts", transaction, command, version))
        return self.facts


def test_proves_exact_latest_draft_using_same_transaction_without_audit():
    harness, transaction = Harness(), object()
    result = harness.service.prove(transaction, query=QUERY)
    assert result.version is FIXED
    assert result.facts is FACTS
    assert result.content_fingerprint == FIXED.content_fingerprint
    assert result.verified_at == NOW
    assert harness.calls == [
        ("lock", transaction, dict(project_id=PROJECT, section_id=SECTION,
                                   version_id=VERSION)),
        ("facts", transaction, QUERY, FIXED),
    ]


@pytest.mark.parametrize("version", [
    None, replace(FIXED, version_state="IN_REVIEW"),
    replace(FIXED, solution_section_version_id=uuid.uuid4()),
    replace(FIXED, project_id=uuid.uuid4()),
    replace(FIXED, content_fingerprint=b"bad"),
])
def test_missing_stale_or_malformed_source_fails_closed(version):
    harness = Harness()
    harness.version = version
    with pytest.raises(SectionReviewReadinessError):
        harness.service.prove(object(), query=QUERY)
    assert all(call[0] != "facts" for call in harness.calls)


@pytest.mark.parametrize("dimension", [
    "integrity", "content", "requirements", "evidence", "trace", "spec",
])
@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE"])
def test_each_non_pass_current_dimension_blocks_review(dimension, status):
    harness = Harness()
    harness.facts = replace(FACTS, **{dimension: status})
    with pytest.raises(SectionReviewReadinessError):
        harness.service.prove(object(), query=QUERY)


def test_source_exception_or_invalid_query_never_becomes_ready():
    harness = Harness()
    harness.service = SectionReviewReadinessService(
        repository=SimpleNamespace(lock_latest=lambda *_args, **_kwargs: FIXED),
        current=SimpleNamespace(facts=lambda *_args, **_kwargs: 1))
    with pytest.raises(SectionReviewReadinessError):
        harness.service.prove(object(), query=QUERY)
    with pytest.raises(SectionReviewReadinessError):
        harness.service.prove(None, query=QUERY)
    with pytest.raises(ValueError):
        SectionCurrentFactQuery(b"short", QUERY.trace_id, PROJECT, SECTION, VERSION)
