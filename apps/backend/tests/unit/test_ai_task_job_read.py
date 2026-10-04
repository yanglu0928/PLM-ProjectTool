from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from plm_assistant.modules.ai.infrastructure.task_job_read import (
    SqlAlchemyAITaskJobReadRepository,
)
from plm_assistant.modules.jobs.application.authorized_read import JobReadError, JobReadFacts


class AITaskJobReadRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.job_id, self.project_id, self.actor_id = uuid4(), uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        self.job = SimpleNamespace(
            job_id=self.job_id, owner_module="ai", job_type="AI_TASK_EXECUTE",
            scope="PROJECT", project_id=self.project_id, actor_ref=self.actor_id,
            state="PENDING", attempt_count=0, lock_version=0,
        )
        self.task = SimpleNamespace(
            task_state="QUEUED", suggestion_state="NONE", retryable=None,
        )
        self.facts = JobReadFacts(
            self.job_id, "ai", "AI_TASK_EXECUTE", "PROJECT", self.project_id,
            self.actor_id, "PENDING", 0, self.now, None, 0,
        )
        self.session = Mock()
        self.session.execute.return_value.one_or_none.return_value = (self.task, self.job)

    def read(self, facts=None):
        with patch(
            "plm_assistant.modules.ai.infrastructure.task_job_read._session",
            return_value=self.session,
        ):
            return SqlAlchemyAITaskJobReadRepository().retryable(
                object(), facts=facts or self.facts,
            )

    def test_new_queued_task_is_consistent_with_pending_job(self):
        self.assertFalse(self.read())

    def test_inconsistent_task_and_job_state_fails_closed(self):
        self.job.state = "RUNNING"
        with self.assertRaises(JobReadError):
            self.read()

    def test_retryability_only_comes_from_matching_terminal_task(self):
        self.job.state = "FAILED"
        self.job.attempt_count = 1
        self.task.task_state = "FAILED"
        self.task.retryable = True
        failed = JobReadFacts(
            self.job_id, "ai", "AI_TASK_EXECUTE", "PROJECT", self.project_id,
            self.actor_id, "FAILED", 1, self.now, self.now, 0,
        )
        self.assertTrue(self.read(failed))


if __name__ == "__main__":
    unittest.main()
