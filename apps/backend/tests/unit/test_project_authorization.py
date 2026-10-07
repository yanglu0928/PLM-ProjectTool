from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, MANAGERS, MEMBER_READERS, POLICIES, ProjectActorFacts, ProjectAuthorizationError,
    ProjectAuthorizationService,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Repo:
    def __init__(self, project_id):
        self.project_id = project_id
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.owner = project_id
        self.calls = 0

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        self.calls += 1
        self.last_lock = lock
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, transaction, *, target, resource_id):
        self.calls += 1
        return self.owner


class ProjectAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.user = uuid.uuid4()
        self.project = uuid.uuid4()
        self.repo = Repo(self.project)
        self.service = ProjectAuthorizationService(unit_of_work=Tx, repository=self.repo)

    def check(self, operation, *, resource_id=None):
        return self.service.require(user_id=self.user, project_id=self.project,
                                    operation=operation, resource_id=resource_id)

    def test_matrix_exact_for_four_roles(self):
        self.assertEqual(len(POLICIES), 109)
        for operation in (
            "REQ_PACKAGE_CREATE", "REQ_PACKAGE_PATCH", "REQ_PACKAGE_ADD",
            "REQ_PACKAGE_REMOVE", "REQ_CREATE",
        ):
            self.assertEqual(POLICIES[operation].roles, frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
            }))
            self.assertTrue(POLICIES[operation].write)
        for operation, roles in (
            ("REQ_PATCH", {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
            ("REQ_DEFER", {"PROJECT_MANAGER", "CUSTOMER_MANAGER"}),
            ("REQ_REJECT", {"PROJECT_MANAGER", "CUSTOMER_MANAGER"}),
            ("REQ_ARCHIVE", {"PROJECT_MANAGER"}),
        ):
            self.assertEqual(POLICIES[operation].roles, roles)
            self.assertTrue(POLICIES[operation].write)
        self.assertEqual(POLICIES["SURVEY_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_CREATE"].write)
        self.assertEqual(POLICIES["SURVEY_VERSION_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_VERSION_CREATE"].write)
        self.assertEqual(POLICIES["SURVEY_VERSION_VALIDATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_VERSION_VALIDATE"].write)
        for operation in (
            "SURVEY_LIST", "SURVEY_GET", "SURVEY_VERSION_LIST",
            "SURVEY_VERSION_GET",
        ):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["SURVEY_PATCH"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_PATCH"].write)
        self.assertEqual(POLICIES["SURVEY_ARCHIVE"].roles,
                         frozenset({"PROJECT_MANAGER"}))
        self.assertTrue(POLICIES["SURVEY_ARCHIVE"].write)
        self.assertEqual(POLICIES["SURVEY_VERSION_SUBMIT_REVIEW"].roles,
                         frozenset({"PROJECT_MANAGER"}))
        self.assertTrue(POLICIES["SURVEY_VERSION_SUBMIT_REVIEW"].write)
        self.assertEqual(POLICIES["SURVEY_ROUND_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_ROUND_CREATE"].write)
        for operation in ("SURVEY_ROUND_LIST", "SURVEY_ROUND_GET"):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["SURVEY_ROUND_PATCH"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_ROUND_PATCH"].write)
        for operation in (
            "SURVEY_ROUND_OPEN", "SURVEY_ROUND_CLOSE", "SURVEY_ROUND_CANCEL",
        ):
            self.assertEqual(POLICIES[operation].roles,
                             frozenset({"PROJECT_MANAGER"}))
            self.assertTrue(POLICIES[operation].write)
        self.assertEqual(POLICIES["SURVEY_ASSIGNMENT_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_ASSIGNMENT_CREATE"].write)
        for operation in ("SURVEY_ASSIGNMENT_LIST", "SURVEY_ASSIGNMENT_GET"):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["SURVEY_RESPONSE_RECORD"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["SURVEY_RESPONSE_RECORD"].write)
        self.assertEqual(POLICIES["SURVEY_ASSIGNMENT_SUBMIT"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["SURVEY_ASSIGNMENT_SUBMIT"].write)
        for operation in ("SURVEY_ASSIGNMENT_VALIDATE", "SURVEY_ASSIGNMENT_RETURN"):
            self.assertEqual(POLICIES[operation].roles, frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
            }))
            self.assertTrue(POLICIES[operation].write)
        self.assertEqual(POLICIES["SURVEY_CONCLUSION_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_CONCLUSION_CREATE"].write)
        self.assertEqual(POLICIES["SURVEY_CONCLUSION_VALIDATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["SURVEY_CONCLUSION_VALIDATE"].write)
        self.assertEqual(POLICIES["SURVEY_CONCLUSION_SUBMIT_REVIEW"].roles,
                         frozenset({"PROJECT_MANAGER"}))
        self.assertTrue(POLICIES["SURVEY_CONCLUSION_SUBMIT_REVIEW"].write)
        for operation in ("SURVEY_CONCLUSION_LIST", "SURVEY_CONCLUSION_GET"):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["HND_ANALYSIS_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["HND_ANALYSIS_CREATE"].write)
        self.assertEqual(POLICIES["HND_VERSION_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["HND_VERSION_CREATE"].write)
        self.assertEqual(POLICIES["HND_VERSION_VALIDATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["HND_VERSION_VALIDATE"].write)
        self.assertEqual(POLICIES["HND_VERSION_SUBMIT_REVIEW"].roles,
                         {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["HND_VERSION_SUBMIT_REVIEW"].write)
        for operation in (
            "HND_ANALYSIS_LIST", "HND_ANALYSIS_GET", "HND_VERSION_LIST",
            "HND_VERSION_GET", "HND_VERSION_ITEM_LIST",
        ):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["HND_ANALYSIS_PATCH"].roles, {
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        })
        self.assertTrue(POLICIES["HND_ANALYSIS_PATCH"].write)
        self.assertEqual(POLICIES["HND_ANALYSIS_ARCHIVE"].roles,
                         {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["HND_ANALYSIS_ARCHIVE"].write)
        self.assertEqual(POLICIES["HND_ACTION_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))
        self.assertTrue(POLICIES["HND_ACTION_CREATE"].write)
        self.assertEqual(POLICIES["HND_ACTION_PATCH"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["HND_ACTION_PATCH"].write)
        self.assertIsNone(POLICIES["HND_ACTION_PATCH"].target)
        self.assertEqual(POLICIES["HND_ACTION_START"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["HND_ACTION_START"].write)
        self.assertEqual(POLICIES["HND_ACTION_SUBMIT"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["HND_ACTION_SUBMIT"].write)
        self.assertEqual(POLICIES["HND_ACTION_VERIFY"].roles, frozenset({
            "PROJECT_MANAGER", "CUSTOMER_MANAGER",
        }))
        self.assertTrue(POLICIES["HND_ACTION_VERIFY"].write)
        for operation in ("HND_ACTION_CLOSE", "HND_ACTION_CANCEL"):
            self.assertEqual(POLICIES[operation].roles, {"PROJECT_MANAGER"})
            self.assertTrue(POLICIES[operation].write)
        for operation in ("HND_ACTION_LIST", "HND_ACTION_GET"):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["RAG_RETRIEVAL_CREATE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
        }))
        self.assertTrue(POLICIES["RAG_RETRIEVAL_CREATE"].write)
        self.assertEqual(POLICIES["RAG_RETRIEVAL_EXECUTE"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
        }))
        self.assertTrue(POLICIES["RAG_RETRIEVAL_EXECUTE"].write)
        for operation in (
            "RAG_RETRIEVAL_GET", "RAG_RETRIEVAL_RESULT_GET", "RAG_CONTEXT_GET",
        ):
            self.assertEqual(POLICIES[operation].roles, ALL_MEMBERS)
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["AI_TASK_CREATE"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
        self.assertTrue(POLICIES["AI_TASK_CREATE"].write)
        self.assertEqual(POLICIES["AI_TASK_OPTIONS_GET"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
        self.assertFalse(POLICIES["AI_TASK_OPTIONS_GET"].write)
        self.assertTrue(POLICIES["AI_TASK_OPTIONS_GET"].lock_reads)
        self.assertEqual(POLICIES["AI_TASK_EXECUTE"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
        self.assertTrue(POLICIES["AI_TASK_EXECUTE"].write)
        self.assertEqual(POLICIES["AI_TASK_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["AI_TASK_GET"].write)
        self.assertEqual(POLICIES["AI_TASK_LIST"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
        }))
        self.assertFalse(POLICIES["AI_TASK_LIST"].write)
        self.assertEqual(POLICIES["AI_TASK_INVOCATION_LIST"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
        }))
        self.assertFalse(POLICIES["AI_TASK_INVOCATION_LIST"].write)
        self.assertEqual(POLICIES["AI_TASK_SUGGESTION_GET"].roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
        }))
        self.assertFalse(POLICIES["AI_TASK_SUGGESTION_GET"].write)
        self.assertTrue(POLICIES["AI_TASK_SUGGESTION_GET"].lock_reads)
        self.assertEqual(POLICIES["EGRESS_PREVIEW_CREATE"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"})
        self.assertTrue(POLICIES["EGRESS_PREVIEW_CREATE"].write)
        self.assertEqual(POLICIES["EGRESS_PREVIEW_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["EGRESS_PREVIEW_GET"].write)
        self.assertTrue(POLICIES["EGRESS_PREVIEW_GET"].lock_reads)
        for operation in ("EGRESS_AUTHORIZE", "EGRESS_REVOKE"):
            self.assertEqual(POLICIES[operation].roles,
                             {"PROJECT_MANAGER", "CUSTOMER_MANAGER"})
            self.assertTrue(POLICIES[operation].write)
        self.assertEqual(POLICIES["TRACE_LINK_SUPERSEDE"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["TRACE_LINK_SUPERSEDE"].write)
        self.assertEqual(POLICIES['DOCUMENT_PARSE_PROCESS'].roles,
                         {'PROJECT_MANAGER', 'IMPLEMENTATION_MEMBER', 'CUSTOMER_MANAGER'})
        self.assertTrue(POLICIES['DOCUMENT_PARSE_PROCESS'].write)
        self.assertEqual(POLICIES['JOB_PROJECT_CANCEL'].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES['JOB_PROJECT_CANCEL'].lock_reads)
        self.assertFalse(POLICIES['JOB_PROJECT_CANCEL'].write)
        self.assertEqual(POLICIES['JOB_PROJECT_RETRY'].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES['JOB_PROJECT_RETRY'].lock_reads)
        self.assertTrue(POLICIES['JOB_PROJECT_RETRY'].write)
        self.assertEqual(POLICIES['JOB_PROJECT_LIST'].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES['JOB_PROJECT_LIST'].lock_reads)
        self.assertFalse(POLICIES['JOB_PROJECT_LIST'].write)
        self.assertEqual(POLICIES['JOB_PROJECT_GET'].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES['JOB_PROJECT_GET'].lock_reads)
        self.assertFalse(POLICIES['JOB_PROJECT_GET'].write)
        self.assertEqual(POLICIES['AUDIT_PROJECT_CANCEL'].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES['AUDIT_PROJECT_CANCEL'].write)
        self.assertTrue(POLICIES['AUDIT_PROJECT_CANCEL'].lock_reads)
        self.assertEqual(POLICIES["AUDIT_PROJECT_EXPORT"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["AUDIT_PROJECT_EXPORT"].write)
        for operation in ("AUDIT_PROJECT_LIST", "AUDIT_PROJECT_GET"):
            self.assertEqual(POLICIES[operation].roles, {"PROJECT_MANAGER"})
            self.assertFalse(POLICIES[operation].write)
            self.assertTrue(POLICIES[operation].lock_reads)
        self.assertEqual(POLICIES["REVIEW_DECIDE"].roles, ALL_MEMBERS)
        self.assertTrue(POLICIES["REVIEW_DECIDE"].write)
        self.assertEqual(POLICIES["REVIEW_WITHDRAW"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["REVIEW_WITHDRAW"].write)
        self.assertEqual(POLICIES["REVIEW_START_ROUND"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["REVIEW_START_ROUND"].write)
        self.assertEqual(POLICIES["REVIEW_CREATE"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["REVIEW_CREATE"].write)
        self.assertEqual(POLICIES["REVIEW_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["REVIEW_GET"].write)
        self.assertTrue(POLICIES["REVIEW_GET"].lock_reads)
        self.assertEqual(POLICIES["WORKFLOW_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["WORKFLOW_GET"].write)
        self.assertTrue(POLICIES["WORKFLOW_GET"].lock_reads)
        self.assertEqual(POLICIES["WORKFLOW_START"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["WORKFLOW_START"].write)
        self.assertEqual(POLICIES["WORKFLOW_CHECKLIST_RECORD"].roles,
                         {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["WORKFLOW_CHECKLIST_RECORD"].write)
        self.assertEqual(POLICIES["WORKFLOW_TRANSITION"].roles,
                         {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["WORKFLOW_TRANSITION"].write)
        self.assertEqual(POLICIES["TRACE_LINK_CREATE"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
        self.assertTrue(POLICIES["TRACE_LINK_CREATE"].write)
        self.assertEqual(POLICIES["TRACE_LINK_REVOKE"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["TRACE_LINK_REVOKE"].write)
        self.assertEqual(POLICIES["TRACE_GRAPH_READ"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["TRACE_GRAPH_READ"].write)
        self.assertTrue(POLICIES["TRACE_GRAPH_READ"].lock_reads)
        self.assertEqual(len(ALL_MEMBERS), 4)
        for operation, policy in POLICIES.items():
            for role in ALL_MEMBERS:
                self.repo.role = role
                resource = uuid.uuid4() if policy.target else None
                with self.subTest(operation=operation, role=role):
                    if role in policy.roles:
                        self.assertEqual(self.check(operation, resource_id=resource).project_role, role)
                    else:
                        with self.assertRaises(ProjectAuthorizationError) as caught:
                            self.check(operation, resource_id=resource)
                        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_unknown_or_invalid_request_denied_before_repository(self):
        for operation, resource in (("UNKNOWN", None), ("PROJECT_GET", uuid.uuid4()),
                                    ("PROJECT_MEMBER_PATCH", None)):
            with self.subTest(operation=operation), self.assertRaises(ProjectAuthorizationError):
                self.check(operation, resource_id=resource)
        self.assertEqual(self.repo.calls, 0)

    def test_workflow_read_locks_current_facts_but_allows_archived_read(self):
        self.repo.state = "ARCHIVED"
        self.assertEqual(self.check("WORKFLOW_GET").operation, "WORKFLOW_GET")
        self.assertTrue(self.repo.last_lock)

    def test_missing_member_and_cross_project_target_are_hidden(self):
        self.repo.role = None
        with self.assertRaises(ProjectAuthorizationError) as missing:
            self.check("PROJECT_GET")
        self.assertEqual(missing.exception.code, "RESOURCE_NOT_FOUND")
        self.repo.role = "PROJECT_MANAGER"
        self.repo.owner = uuid.uuid4()
        with self.assertRaises(ProjectAuthorizationError) as cross:
            self.check("PROJECT_MEMBER_PATCH", resource_id=uuid.uuid4())
        self.assertEqual(cross.exception.code, "RESOURCE_NOT_FOUND")

    def test_archived_allows_read_but_denies_write(self):
        self.repo.state = "ARCHIVED"
        self.assertEqual(self.check("PROJECT_GET").operation, "PROJECT_GET")
        with self.assertRaises(ProjectAuthorizationError) as archived:
            self.check("PROJECT_PATCH")
        self.assertEqual(archived.exception.code, "PROJECT_ARCHIVED")

    def test_archived_export_is_only_new_write_maintenance_exception(self):
        self.repo.state = "ARCHIVED"
        for operation, policy in POLICIES.items():
            if not policy.write:continue
            resource = uuid.uuid4() if policy.target else None
            if operation == "AUDIT_PROJECT_EXPORT":
                self.assertEqual(self.check(operation).project_role,"PROJECT_MANAGER")
                self.assertTrue(self.repo.last_lock)
            else:
                with self.subTest(operation=operation), self.assertRaises(ProjectAuthorizationError) as denied:
                    self.check(operation,resource_id=resource)
                self.assertEqual(denied.exception.code,"PROJECT_ARCHIVED")

    def test_write_uses_locked_current_facts_in_caller_transaction(self):
        tx = Tx()
        result = self.service.require_in_transaction(
            tx, user_id=self.user, project_id=self.project, operation="PROJECT_PATCH",
        )
        self.assertEqual(result.project_role, "PROJECT_MANAGER")
        self.assertTrue(self.repo.last_lock)
        self.check("PROJECT_GET")
        self.assertFalse(self.repo.last_lock)


if __name__ == "__main__":
    unittest.main()
