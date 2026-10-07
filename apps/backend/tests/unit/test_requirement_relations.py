from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.requirement.application.relations import (
    CreateRequirementRelation, RequirementRelationError,
    RequirementRelationQuery, RequirementRelationService,
    RequirementRelationView, RequirementVersionRef, RevokeRequirementRelation,
    StoredRequirementRelation, SupersedeRequirementRelation,
)


class _Tx:
    def __init__(self):
        self.committed = False
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def commit(self):
        self.committed = True


class RequirementRelationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.left = RequirementVersionRef(uuid.uuid4(), uuid.uuid4())
        self.right = RequirementVersionRef(uuid.uuid4(), uuid.uuid4())
        self.relation = uuid.uuid4()
        self.tx = _Tx()
        self.write_access, self.read_access = Mock(), Mock()
        self.write_access.authenticated_user.return_value = self.actor
        self.read_access.authenticated_user.return_value = self.actor
        self.guard, self.authorization = Mock(), Mock()
        self.authorization.require_in_transaction.side_effect = (
            lambda _tx, **kwargs: AuthorizedProjectAction(
                kwargs["user_id"], kwargs["project_id"],
                kwargs["operation"], "PROJECT_MANAGER"))
        self.repo, self.receipts, self.audit = Mock(unsafe=True), Mock(), Mock()
        self.receipts.reserve.return_value = None
        self.repo.endpoints_exist.return_value = True
        self.repo.create_active.return_value = StoredRequirementRelation(
            self.relation, True)
        self.view = RequirementRelationView(
            self.relation, self.project, self.left, self.right,
            "DEPENDS_ON", "ACTIVE", 0, self.actor, self.now, None)
        self.repo.get.return_value = self.view
        self.service = RequirementRelationService(
            unit_of_work=lambda: self.tx, write_access=self.write_access,
            read_access=self.read_access, license_guard=self.guard,
            authorization=self.authorization, repository=self.repo,
            receipts=self.receipts, audit=self.audit, clock=lambda: self.now)

    def command(self, relation_type="DEPENDS_ON", source=None, target=None):
        return CreateRequirementRelation(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            source or self.left, target or self.right, relation_type,
            str(uuid.uuid4()))

    def test_create_proves_endpoints_cycle_and_audits(self):
        result = self.service.create(self.command())
        self.assertEqual(result, self.view)
        self.assertTrue(self.tx.committed)
        self.repo.assert_acyclic.assert_called_once_with(
            self.tx, project_id=self.project,
            source_version_id=self.left.requirement_version_id,
            target_version_id=self.right.requirement_version_id,
            relation_type="DEPENDS_ON", exclude_relation_id=None)
        self.audit.append.assert_called_once()
        event = self.audit.append.call_args.args[1]
        self.assertEqual(event.action, "REQUIREMENT_RELATION_CREATED")

    def test_symmetric_input_is_canonical_before_persistence(self):
        ordered = sorted(
            (self.left, self.right),
            key=lambda item: (
                item.requirement_id.bytes,
                item.requirement_version_id.bytes))
        self.view = RequirementRelationView(
            self.relation, self.project, ordered[0], ordered[1],
            "DUPLICATES", "ACTIVE", 0, self.actor, self.now, None)
        self.repo.get.return_value = self.view
        result = self.service.create(self.command(
            "DUPLICATES", source=ordered[1], target=ordered[0]))
        self.assertEqual((result.source, result.target), tuple(ordered))
        call = self.repo.create_active.call_args.kwargs
        self.assertEqual((call["source"], call["target"]), tuple(ordered))

    def test_cycle_and_missing_endpoint_fail_closed(self):
        self.repo.assert_acyclic.side_effect = RequirementRelationError(
            "REQUIREMENT_RELATION_CYCLE")
        with self.assertRaisesRegex(
                RequirementRelationError, "REQUIREMENT_RELATION_CYCLE"):
            self.service.create(self.command())
        self.repo.create_active.assert_not_called()
        self.repo.assert_acyclic.side_effect = None
        self.repo.endpoints_exist.return_value = False
        with self.assertRaises(RequirementRelationError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_list_is_authorized_and_stably_paged(self):
        older = RequirementRelationView(
            uuid.uuid4(), self.project, self.right, self.left,
            "RELATED_TO", "REVOKED", 1, self.actor, self.now, None)
        self.repo.list_relations.return_value = (self.view, older)
        page = self.service.list(RequirementRelationQuery(
            b"s" * 32, uuid.uuid4(), self.project), page_size=1)
        self.assertEqual(page.items, (self.view,))
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_relation_id, self.relation)
        self.authorization.require_in_transaction.assert_called_with(
            self.tx, user_id=self.actor, project_id=self.project,
            operation="REQ_RELATION_LIST")

    def test_invalid_self_edge_and_secrets_are_rejected(self):
        command = self.command(target=RequirementVersionRef(
            uuid.uuid4(), self.left.requirement_version_id))
        with self.assertRaises(RequirementRelationError) as caught:
            self.service.create(command)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        rendered = repr(self.command())
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)

    def test_revoke_is_atomic_and_replayable(self):
        revoked = RequirementRelationView(
            self.relation, self.project, self.left, self.right,
            "DEPENDS_ON", "REVOKED", 1, self.actor, self.now, None)
        self.repo.lock_active.return_value = self.view
        self.repo.get.return_value = revoked
        result = self.service.revoke(RevokeRequirementRelation(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.relation, str(uuid.uuid4())))
        self.assertEqual(result, revoked)
        self.repo.revoke_active.assert_called_once_with(
            self.tx, project_id=self.project, relation_id=self.relation)
        self.assertEqual(
            self.receipts.complete.call_args.kwargs["result"].status_code, 200)
        self.assertEqual(
            self.audit.append.call_args.args[1].action,
            "REQUIREMENT_RELATION_REVOKED")

    def test_supersede_excludes_old_edge_and_binds_replacement(self):
        replacement_id = uuid.uuid4()
        replacement = RequirementRelationView(
            replacement_id, self.project, self.left,
            RequirementVersionRef(uuid.uuid4(), uuid.uuid4()),
            "PARENT_OF", "ACTIVE", 0, self.actor, self.now, None)
        self.repo.lock_active.return_value = self.view
        self.repo.create_active.return_value = StoredRequirementRelation(
            replacement_id, True)
        self.repo.get.return_value = replacement
        self.repo.replacement_matches.return_value = True
        result = self.service.supersede(SupersedeRequirementRelation(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.relation, replacement.source, replacement.target,
            replacement.relation_type, str(uuid.uuid4())))
        self.assertEqual(result, replacement)
        cycle = self.repo.assert_acyclic.call_args.kwargs
        self.assertEqual(cycle["exclude_relation_id"], self.relation)
        self.repo.supersede_active.assert_called_once_with(
            self.tx, project_id=self.project, relation_id=self.relation,
            replacement_id=replacement_id)
        self.assertEqual(
            self.receipts.complete.call_args.kwargs["result"].status_code, 201)


if __name__ == "__main__":
    unittest.main()
