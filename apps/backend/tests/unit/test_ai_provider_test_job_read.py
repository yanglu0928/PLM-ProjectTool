from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.ai.application.provider_test_job_read_projection import ProviderTestJobReadProjection
from plm_assistant.modules.ai.infrastructure.provider_test_job_read import SqlAlchemyProviderTestJobReadRepository
from plm_assistant.modules.jobs.application.authorized_read import JobReadError, JobReadFacts


class ProviderTestJobReadTests(unittest.TestCase):
    def setUp(self):
        self.job, self.actor, self.provider, self.config, self.secret = (uuid4() for _ in range(5))
        self.result = uuid4()
        self.now = datetime.now(timezone.utc)
        self.facts = JobReadFacts(self.job, "ai", "AI_PROVIDER_TEST", "DEPLOYMENT",
                                  None, self.actor, "SUCCEEDED", 1, self.now, self.now, 2)
        self.proof = Mock(result_id=Mock(return_value=self.result))
        self.owner = ProviderTestJobReadProjection(repository=self.proof)

    def test_owner_only_exposes_safe_success_reference(self):
        value = self.owner.project(object(), facts=self.facts, actor_id=uuid4(), project_role=None)
        self.assertEqual((value.result_type, value.result_id, value.retryable),
                         ("AI_PROVIDER_TEST", self.result, False))
        self.assertFalse(hasattr(value, "failure_code"))

    def test_wrong_owner_or_scope_fail_closed(self):
        for change in ({"owner_module": "audit"}, {"scope": "GLOBAL"},
                       {"actor_id": None}):
            with self.subTest(change=change), self.assertRaises(JobReadError):
                self.owner.project(object(), facts=replace(self.facts, **change),
                                   actor_id=self.actor, project_role=None)
        with self.assertRaises(JobReadError):
            self.owner.project(object(), facts=self.facts, actor_id=self.actor,
                               project_role="PROJECT_MANAGER")
        self.proof.result_id.assert_not_called()

    def test_non_success_never_exposes_result(self):
        self.proof.result_id.return_value = None
        for state in ("PENDING", "RUNNING", "RETRY_WAIT", "FAILED", "CANCELLED"):
            facts = replace(self.facts, state=state, attempt_count=0 if state == "PENDING" else 1,
                            completed_at=self.now if state in ("FAILED", "CANCELLED") else None)
            self.assertIsNone(self.owner.project(object(), facts=facts, actor_id=self.actor,
                                                 project_role=None).result_id)
        self.proof.result_id.return_value = self.result
        with self.assertRaises(JobReadError):
            self.owner.project(object(), facts=replace(self.facts, state="FAILED"),
                               actor_id=self.actor, project_role=None)

    def test_sql_proof_rechecks_pair_and_result_coordinates(self):
        repo = SqlAlchemyProviderTestJobReadRepository()
        job = SimpleNamespace(job_id=self.job, owner_module="ai", job_type="AI_PROVIDER_TEST",
                              scope="DEPLOYMENT", project_id=None, actor_ref=self.actor,
                              state="SUCCEEDED", attempt_count=1, lock_version=2,
                              fencing_token=1)
        result = SimpleNamespace(probe_result_id=self.result, job_id=self.job,
                                 ai_provider_id=self.provider, provider_config_version_id=self.config,
                                 secret_record_id=uuid4(),
                                 secret_version_id=self.secret, policy_sha256=b"p" * 32,
                                 probe_id="CHAT_CONNECTIVITY_V1", attempt_no=1,
                                 fencing_token=1, outcome="SUCCEEDED")
        session = Mock()
        session.connection.return_value.dialect.name = "postgresql"
        session.connection.return_value.get_isolation_level.return_value = "READ COMMITTED"
        config = SimpleNamespace(ai_provider_id=self.provider, config_version_no=1,
                                 secret_ref=result.secret_record_id)
        session.get.side_effect = lambda model, _: job if model.__name__ == "JobRow" else config
        session.scalar.return_value = result
        repo._snapshots._leases._session = Mock(return_value=session)
        repo._snapshots._snapshot = Mock(return_value=(self.provider, self.config, 1,
                                                       self.secret, b"p" * 32))
        self.assertEqual(repo.result_id(object(), facts=self.facts), self.result)
        repo._snapshots._snapshot.assert_called_once_with(session, job)
        for field, value in (("ai_provider_id", uuid4()), ("provider_config_version_id", uuid4()),
                             ("secret_version_id", uuid4()), ("policy_sha256", b"q" * 32),
                             ("attempt_no", 2), ("fencing_token", 2), ("outcome", "FAILED")):
            original = getattr(result, field)
            setattr(result, field, value)
            with self.subTest(field=field), self.assertRaises(JobReadError):
                repo.result_id(object(), facts=self.facts)
            setattr(result, field, original)
        job.actor_ref = uuid4()
        with self.assertRaises(JobReadError):
            repo.result_id(object(), facts=self.facts)

    def test_missing_or_failure_result_never_yields_success_reference(self):
        repo = SqlAlchemyProviderTestJobReadRepository()
        session = Mock()
        session.connection.return_value.dialect.name = "postgresql"
        session.connection.return_value.get_isolation_level.return_value = "READ COMMITTED"
        job = SimpleNamespace(job_id=self.job, owner_module="ai",
            job_type="AI_PROVIDER_TEST", scope="DEPLOYMENT", project_id=None,
            actor_ref=self.actor, state="SUCCEEDED", attempt_count=1, lock_version=2,
            fencing_token=1)
        session.get.return_value = job
        session.scalar.return_value = None
        repo._snapshots._leases._session = Mock(return_value=session)
        repo._snapshots._snapshot = Mock(return_value=(self.provider, self.config, 1,
                                                       self.secret, b"p" * 32))
        with self.assertRaises(JobReadError):
            repo.result_id(object(), facts=self.facts)
        job.state = "FAILED"
        self.assertIsNone(repo.result_id(object(), facts=replace(self.facts, state="FAILED")))


if __name__ == "__main__":
    unittest.main()
