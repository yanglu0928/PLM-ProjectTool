"""Latest Outline lock is exact, same-project, and state-sensitive."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from plm_assistant.modules.solution.infrastructure.outline_review_readiness_repository import (
    SqlAlchemyOutlineReviewReadinessRepository,
)


PROJECT, OUTLINE, VERSION = (uuid4() for _ in range(3))


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
    marker = object()
    path = ("plm_assistant.modules.solution.infrastructure."
            "outline_review_readiness_repository")
    with (patch(path + "._session", return_value=session),
          patch(path + ".SqlAlchemyOutlineReadRepository.get_current",
                return_value=marker),
          patch(path + ".SqlAlchemyOutlineVersionReadRepository.get",
                return_value=marker)):
        result = SqlAlchemyOutlineReviewReadinessRepository().lock_latest(
            object(), project_id=PROJECT, outline_id=OUTLINE,
            version_id=VERSION, required_state=required_state)
    return result, session.statements


def test_root_then_latest_version_share_locks_and_fixed_read():
    result, sql = source(Session(
        SimpleNamespace(outline_state="ACTIVE"),
        SimpleNamespace(solution_outline_version_id=VERSION,
                        version_state="DRAFT")))
    assert result is not None
    assert len(sql) == 2
    assert "FOR SHARE OF sol_outlines" in sql[0]
    assert "FOR SHARE OF sol_outline_versions" in sql[1]


def test_terminal_requires_in_review_and_exact_latest_identity():
    assert source(Session(
        SimpleNamespace(outline_state="ACTIVE"),
        SimpleNamespace(solution_outline_version_id=VERSION,
                        version_state="IN_REVIEW")),
        required_state="IN_REVIEW")[0] is not None
    for state in ("DRAFT", "APPROVED"):
        assert source(Session(
            SimpleNamespace(outline_state="ACTIVE"),
            SimpleNamespace(solution_outline_version_id=VERSION,
                            version_state=state)),
            required_state="IN_REVIEW")[0] is None
    assert source(Session(
        SimpleNamespace(outline_state="ACTIVE"),
        SimpleNamespace(solution_outline_version_id=uuid4(),
                        version_state="DRAFT")))[0] is None


def test_missing_or_archived_root_fails_closed():
    assert source(Session(None))[0] is None
    assert source(Session(SimpleNamespace(outline_state="ARCHIVED")))[0] is None
