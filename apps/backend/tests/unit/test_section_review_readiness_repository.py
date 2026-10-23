"""Review source locks parent, section, latest version before fact reads."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from plm_assistant.modules.solution.infrastructure.section_review_readiness_repository import (
    SqlAlchemySectionReviewReadinessRepository,
)


PROJECT, OUTLINE, SECTION, VERSION = (uuid.uuid4() for _ in range(4))


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class Session:
    def __init__(self, *values):
        self.values = iter(values)
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True})))
        return Result(next(self.values))


def source(session, *, required_state="DRAFT"):
    port = SqlAlchemySectionReviewReadinessRepository()
    marker = object()
    with (patch("plm_assistant.modules.solution.infrastructure.section_review_readiness_repository._session",
                return_value=session),
          patch("plm_assistant.modules.solution.infrastructure.section_review_readiness_repository.SqlAlchemyOutlineReadRepository.get_current",
                return_value=marker),
          patch("plm_assistant.modules.solution.infrastructure.section_review_readiness_repository.SqlAlchemySectionReadRepository.get_current",
                return_value=marker),
          patch("plm_assistant.modules.solution.infrastructure.section_review_readiness_repository.SqlAlchemySectionVersionReadRepository.get",
                return_value=marker)):
        return port.lock_latest(object(), project_id=PROJECT,
                                section_id=SECTION, version_id=VERSION,
                                required_state=required_state)


def test_locks_parent_section_latest_then_reconstructs_fixed_source():
    session = Session(OUTLINE, SimpleNamespace(outline_state="ACTIVE"),
                      SimpleNamespace(solution_outline_id=OUTLINE,
                                      section_state="ACTIVE"),
                      SimpleNamespace(solution_section_version_id=VERSION,
                                      version_state="DRAFT"))
    assert source(session) is not None
    assert len(session.statements) == 4
    assert "FOR SHARE OF sol_outlines" in session.statements[1]
    assert "FOR SHARE OF sol_sections" in session.statements[2]
    assert "FOR SHARE OF sol_section_versions" in session.statements[3]


def test_in_review_terminal_lock_requires_exact_latest_state():
    def rows(state):
        return Session(OUTLINE, SimpleNamespace(outline_state="ACTIVE"),
                       SimpleNamespace(solution_outline_id=OUTLINE,
                                       section_state="ACTIVE"),
                       SimpleNamespace(solution_section_version_id=VERSION,
                                       version_state=state))

    assert source(rows("IN_REVIEW"), required_state="IN_REVIEW") is not None
    assert source(rows("DRAFT"), required_state="IN_REVIEW") is None
    assert source(rows("IN_REVIEW")) is None
    assert source(rows("IN_REVIEW"), required_state="APPROVED") is None


def test_stale_latest_or_archived_ancestor_fails_closed():
    for values in (
        (None,),
        (OUTLINE, SimpleNamespace(outline_state="ARCHIVED")),
        (OUTLINE, SimpleNamespace(outline_state="ACTIVE"),
         SimpleNamespace(solution_outline_id=OUTLINE, section_state="ARCHIVED")),
        (OUTLINE, SimpleNamespace(outline_state="ACTIVE"),
         SimpleNamespace(solution_outline_id=OUTLINE, section_state="ACTIVE"),
         SimpleNamespace(solution_section_version_id=uuid.uuid4(),
                         version_state="DRAFT")),
    ):
        assert source(Session(*values)) is None
