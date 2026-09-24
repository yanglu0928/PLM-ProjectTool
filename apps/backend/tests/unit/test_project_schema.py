from __future__ import annotations

import unittest

from sqlalchemy import ForeignKeyConstraint, Index

from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectRow,
)


class ProjectSchemaTests(unittest.TestCase):
    def test_roots_and_scoped_department_fk(self):
        self.assertEqual({ProjectRow.__tablename__, DepartmentRow.__tablename__,
                          ProjectMemberRow.__tablename__},
                         {"prj_projects", "prj_departments", "prj_project_members"})
        self.assertNotIn("current_stage", ProjectRow.__table__.columns)
        scoped = [constraint for constraint in ProjectMemberRow.__table__.constraints
                  if isinstance(constraint, ForeignKeyConstraint)
                  and constraint.name == "fk_prj_members__department_project"]
        self.assertEqual(len(scoped), 1)
        self.assertEqual([column.name for column in scoped[0].columns],
                         ["department_id", "project_id"])
        self.assertEqual([element.column.name for element in scoped[0].elements],
                         ["department_id", "project_id"])

    def test_effective_members_have_unique_user(self):
        indices = {item.name: item for item in ProjectMemberRow.__table__.indexes
                   if isinstance(item, Index)}
        self.assertTrue(indices["uq_prj_members__user_active"].unique)
        self.assertIn("REMOVED", str(indices["uq_prj_members__user_active"].dialect_options["postgresql"]["where"]))


if __name__ == "__main__":
    unittest.main()
