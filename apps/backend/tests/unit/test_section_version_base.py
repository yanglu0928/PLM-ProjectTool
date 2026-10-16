from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy.dialects import postgresql

from plm_assistant.modules.solution.infrastructure.section_version_base import (
    SqlAlchemyCurrentSectionVersionBase,
)


PROJECT = uuid.uuid4()
OUTLINE = uuid.uuid4()
SECTION = uuid.uuid4()
VERSION = uuid.uuid4()
PREDECESSOR = uuid.uuid4()


def root(**values):
    return SimpleNamespace(**values)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def one_or_none(self):
        return self.value


class _Session:
    def __init__(self, *values):
        self.values = iter(values)
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True})))
        return _Result(next(self.values))


def outline(*, state="ACTIVE", pointer=None, lock=3):
    return root(solution_outline_id=OUTLINE, project_id=PROJECT,
                outline_state=state, current_approved_version_ref=pointer,
                lock_version=lock)


def section(*, parent=OUTLINE, state="ACTIVE", pointer=None, lock=4):
    return root(solution_section_id=SECTION, solution_outline_id=parent,
                project_id=PROJECT, section_state=state,
                current_approved_version_ref=pointer, lock_version=lock)


def version(*, number=1, predecessor=None):
    return root(solution_section_version_id=VERSION, solution_section_id=SECTION,
                project_id=PROJECT, version_no=number,
                supersedes_version_ref=predecessor)


class SectionVersionBaseTests(unittest.TestCase):
    def setUp(self):
        self.port = SqlAlchemyCurrentSectionVersionBase()
        self.transaction = object()

    def current(self, session, **overrides):
        values = dict(transaction=self.transaction, project_id=PROJECT,
                      section_id=SECTION)
        values.update(overrides)
        with patch("plm_assistant.modules.solution.infrastructure.section_version_base._session",
                   return_value=session):
            return self.port.current(**values)

    def test_first_version_and_parent_before_section_lock(self):
        session = _Session(OUTLINE, (outline(), None), (section(), None), None)
        value = self.current(session)
        self.assertEqual((value.project_id, value.solution_outline_id,
                          value.solution_section_id), (PROJECT, OUTLINE, SECTION))
        self.assertEqual((value.next_version_no, value.supersedes_version_id), (1, None))
        self.assertEqual((value.outline_lock_version, value.section_lock_version), (3, 4))
        self.assertEqual(len(session.statements), 4)
        self.assertNotIn("FOR UPDATE", session.statements[0])
        self.assertIn("FOR UPDATE OF sol_outlines", session.statements[1])
        self.assertIn("FOR UPDATE OF sol_sections", session.statements[2])
        self.assertIn("FOR SHARE OF sol_section_versions", session.statements[3])

    def test_next_version_uses_latest_fixed_predecessor(self):
        session = _Session(OUTLINE, (outline(), None), (section(), None),
                           version(number=5, predecessor=PREDECESSOR), 4)
        value = self.current(session)
        self.assertEqual((value.next_version_no, value.supersedes_version_id),
                         (6, VERSION))
        self.assertIn("FOR SHARE OF sol_section_versions", session.statements[4])

    def test_invalid_identity_or_missing_root(self):
        self.assertIsNone(self.current(_Session(), project_id=uuid.UUID(int=0)))
        self.assertIsNone(self.current(_Session(), section_id="not uuid"))
        self.assertIsNone(self.current(_Session(None)))
        self.assertIsNone(self.current(_Session(OUTLINE, None)))
        self.assertIsNone(self.current(_Session(OUTLINE, (outline(), None), None)))

    def test_inactive_parent_or_section_and_reparent_fail_closed(self):
        for values in (
            (outline(state="ARCHIVED"), section()),
            (outline(lock=-1), section()),
            (outline(), section(state="ARCHIVED")),
            (outline(), section(lock=-1)),
            (outline(), section(parent=uuid.uuid4())),
        ):
            with self.subTest(values=values):
                self.assertIsNone(self.current(_Session(OUTLINE, (values[0], None),
                                                         (values[1], None))))

    def test_inconsistent_approved_pointers_rejected(self):
        for session in (
            _Session(OUTLINE, (outline(pointer=uuid.uuid4()), None)),
            _Session(OUTLINE, (outline(), None),
                     (section(pointer=uuid.uuid4()), None)),
        ):
            with self.subTest(session=session):
                with self.assertRaisesRegex(RuntimeError, "approved pointer is inconsistent"):
                    self.current(session)

    def test_invalid_latest_version_fails_closed(self):
        for latest in (version(number=0), version(number=2_147_483_647),
                       version(number=True), version(number=1, predecessor=PREDECESSOR),
                       version(number=2),
                       root(solution_section_version_id=uuid.UUID(int=0), version_no=1)):
            with self.subTest(latest=latest):
                self.assertIsNone(self.current(_Session(
                    OUTLINE, (outline(), None), (section(), None), latest)))

    def test_broken_predecessor_number_fails_closed(self):
        for predecessor_no in (None, 1, 3):
            with self.subTest(predecessor_no=predecessor_no):
                self.assertIsNone(self.current(_Session(
                    OUTLINE, (outline(), None), (section(), None),
                    version(number=5, predecessor=PREDECESSOR), predecessor_no)))


if __name__ == "__main__":
    unittest.main()
