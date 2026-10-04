import unittest
import uuid
from types import SimpleNamespace

from plm_assistant.modules.workflow.infrastructure.start_repository import (
    SqlAlchemyWorkflowStartRepository, WorkflowStartRepositoryError,
)


class WorkflowStartRepositoryInputTests(unittest.TestCase):
    def setUp(self):
        self.repo = SqlAlchemyWorkflowStartRepository()
        self.project = uuid.uuid4()

    def test_rejects_bad_identity_or_version_before_database_access(self):
        for project, version in (
            (None, 0), (uuid.UUID(int=0), 0), (self.project, -1),
            (self.project, True), (self.project, 2**63),
        ):
            with self.subTest(project=project, version=version):
                with self.assertRaises(WorkflowStartRepositoryError) as caught:
                    self.repo.start(SimpleNamespace(), project_id=project,
                                    expected_version=version)
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_requires_active_real_unit_of_work(self):
        with self.assertRaises(WorkflowStartRepositoryError) as caught:
            self.repo.start(SimpleNamespace(session=object()), project_id=self.project,
                            expected_version=0)
        self.assertEqual(caught.exception.code, "WORKFLOW_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
