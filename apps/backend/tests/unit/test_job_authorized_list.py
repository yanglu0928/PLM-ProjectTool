import unittest
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.authorized_list import AuthorizedJobListService, JobListQuery, JobListCandidates
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobOwnerProjection, JobReadError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class JobListTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid4(), uuid4()
        self.facts = JobReadFacts(uuid4(), 'document', 'DOCUMENT_PARSE', 'PROJECT', self.project, self.actor, 'PENDING', 0, datetime.now(timezone.utc), None)
        self.tx = Mock(); self.repo, self.owner, self.access, self.projects, self.guard = Mock(), Mock(), Mock(), Mock(), Mock()
        self.access.authenticated_user.return_value = self.actor
        self.access.authorized_admin.return_value = self.actor
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(self.actor, self.project, 'JOB_PROJECT_LIST', 'PROJECT_MANAGER')
        self.repo.list.return_value = JobListCandidates((self.facts,), False)
        self.repo.get.return_value = self.facts
        self.owner.project.return_value = JobOwnerProjection(self.facts.job_id, False)
        self.service = AuthorizedJobListService(unit_of_work=lambda: nullcontext(self.tx), project_access=self.access,
            deployment_access=self.access, projects=self.projects, license_guard=self.guard, repository=self.repo,
            owners={('document', 'DOCUMENT_PARSE'): self.owner})
        self.query = JobListQuery(b'q' * 32, self.project, uuid4())

    def test_same_uow_current_policy_and_no_commit(self):
        page = self.service.list(self.query)
        self.assertEqual(page.items[0].facts, self.facts)
        self.repo.list.assert_called_once_with(self.tx, project_id=self.project, scope=None, actor_id=None,
            owner_types=(('document', 'DOCUMENT_PARSE'),), before=None, limit=50)
        self.projects.require_in_transaction.assert_called_once_with(self.tx, user_id=self.actor, project_id=self.project, operation='JOB_PROJECT_LIST')
        self.tx.commit.assert_not_called()

    def test_customer_filters_before_query_and_rechecks_actor(self):
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(self.actor, self.project, 'JOB_PROJECT_LIST', 'CUSTOMER_MEMBER')
        self.service.list(self.query)
        self.assertEqual(self.repo.list.call_args.kwargs['actor_id'], self.actor)
        self.repo.list.return_value = JobListCandidates((replace(self.facts, actor_id=uuid4()),), False)
        with self.assertRaises(JobReadError): self.service.list(self.query)

    def test_hidden_candidate_empty_page_advances_private_position(self):
        self.repo.list.return_value = JobListCandidates((self.facts,), True)
        self.owner.project.side_effect = JobReadError('RESOURCE_NOT_FOUND')
        page = self.service.list(self.query)
        self.assertEqual(page.items, ())
        self.assertEqual(page.next_position, (self.facts.created_at, self.facts.job_id))
        self.assertTrue(page.has_more)
        self.repo.get.assert_not_called(); self.tx.commit.assert_not_called()

    def test_unknown_source_changed_fact_and_exception_fail_closed(self):
        self.owner.project.side_effect = JobReadError()
        with self.assertRaises(JobReadError): self.service.list(self.query)
        self.owner.project.side_effect = None
        self.repo.get.return_value = replace(self.facts, lock_version=1)
        with self.assertRaises(JobReadError): self.service.list(self.query)
        self.repo.list.side_effect = RuntimeError('private SQL')
        with self.assertRaises(JobReadError) as cm: self.service.list(self.query)
        self.assertEqual(str(cm.exception), 'JOB_UNAVAILABLE')

    def test_strict_pagination_shapes_scope_and_sort(self):
        for changes in ({'page_size': True}, {'page_size': 201}, {'before': (datetime.now(), uuid4())}, {'scope': 'GLOBAL'}):
            with self.assertRaises(JobReadError): replace(self.query, **changes)
        with self.assertRaises(JobReadError): JobListCandidates((self.facts, self.facts), False)
        with self.assertRaises(JobReadError): JobListCandidates((), True)
        self.repo.list.return_value = JobListCandidates((self.facts,), False)
        with self.assertRaises(JobReadError): self.service.list(replace(self.query, project_id=None))

    def test_missing_session_and_invalid_query_before_repository(self):
        self.access.authenticated_user.return_value = None
        with self.assertRaises(JobReadError): self.service.list(self.query)
        self.repo.list.assert_not_called()
        with self.assertRaises(JobReadError): self.service.list(object())
