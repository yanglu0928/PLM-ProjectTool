from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.prototype.application.requirement_links import (
    CreateRequirementPrototypeLink, RequirementPrototypeCoverage,
    RequirementPrototypeLinkError, RequirementPrototypeLinkQuery,
    RequirementPrototypeLinkService, RequirementPrototypeLinkView,
    RevokeRequirementPrototypeLink, StoredRequirementPrototypeLink,
    SupersedeRequirementPrototypeLink, UncoveredAcceptanceCriterion,
)


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class RequirementPrototypeLinkTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.prototype, self.prototype_version = uuid.uuid4(), uuid.uuid4()
        self.covered, self.uncovered = uuid.uuid4(), uuid.uuid4()
        self.link = uuid.uuid4()
        self.coverage = RequirementPrototypeCoverage(
            (self.covered,),
            (UncoveredAcceptanceCriterion(self.uncovered, "Needs hardware"),),
        )
        self.tx = _Tx()
        self.write_access, self.read_access = Mock(), Mock()
        self.write_access.authenticated_user.return_value = self.actor
        self.read_access.authenticated_user.return_value = self.actor
        self.guard, self.authorization = Mock(), Mock()
        self.authorization.require_in_transaction.side_effect = (
            lambda _tx, **kwargs: AuthorizedProjectAction(
                kwargs["user_id"], kwargs["project_id"], kwargs["operation"],
                "PROJECT_MANAGER",
            )
        )
        self.repo, self.reader, self.validator = Mock(unsafe=True), Mock(), Mock()
        self.receipts, self.audit = Mock(), Mock()
        self.receipts.reserve.return_value = None
        self.repo.prove_current_endpoints.return_value = (
            self.covered, self.uncovered,
        )
        self.reader.get.return_value = SimpleNamespace(
            version_state="APPROVED",
            requirement_refs=(SimpleNamespace(
                requirement_id=self.requirement,
                requirement_version_id=self.requirement_version,
            ),),
        )
        self.validator.current_facts.return_value = object()
        self.repo.create_active.return_value = StoredRequirementPrototypeLink(
            self.link, True,
        )
        self.view = RequirementPrototypeLinkView(
            self.link, self.project, self.requirement, self.requirement_version,
            self.prototype, self.prototype_version, "ILLUSTRATES",
            self.coverage, "ACTIVE", 0, self.actor, self.now, None,
        )
        self.repo.get.return_value = self.view
        self.repo.lock_active.return_value = self.view
        self.service = RequirementPrototypeLinkService(
            unit_of_work=lambda: self.tx, write_access=self.write_access,
            read_access=self.read_access, license_guard=self.guard,
            authorization=self.authorization, repository=self.repo,
            version_reader=self.reader, current_validator=self.validator,
            receipts=self.receipts, audit=self.audit, clock=lambda: self.now,
        )

    def command(self, coverage=None):
        return CreateRequirementPrototypeLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.requirement, self.requirement_version, self.prototype,
            self.prototype_version, "ILLUSTRATES", coverage or self.coverage,
            str(uuid.uuid4()),
        )

    def test_create_proves_full_current_endpoint_and_audits(self):
        result = self.service.create(self.command())
        self.assertEqual(result, self.view)
        self.assertTrue(self.tx.committed)
        self.repo.prove_current_endpoints.assert_called_once()
        self.validator.current_facts.assert_called_once()
        self.assertEqual(
            self.audit.append.call_args.args[1].action,
            "REQUIREMENT_PROTOTYPE_LINK_CREATED",
        )

    def test_coverage_is_sorted_and_reason_is_normalized(self):
        lower, upper = sorted((self.covered, self.uncovered), key=lambda x: x.bytes)
        coverage = RequirementPrototypeCoverage(
            (upper, lower),
            (UncoveredAcceptanceCriterion(uuid.uuid4(), "  full width Ａ  "),),
        )
        self.repo.prove_current_endpoints.return_value = (
            lower, upper,
            coverage.uncovered_acceptance_criteria[0].acceptance_criterion_ref,
        )
        self.repo.get.side_effect = lambda *_args, **_kwargs: self.view
        with self.assertRaises(RequirementPrototypeLinkError):
            self.service.create(self.command(coverage))
        call = self.repo.create_active.call_args.kwargs
        self.assertEqual(call["coverage"].covered_acceptance_criterion_refs,
                         (lower, upper))
        self.assertEqual(call["coverage"].uncovered_acceptance_criteria[0].reason,
                         "full width A")

    def test_gap_or_foreign_criterion_fails_before_insert(self):
        self.repo.prove_current_endpoints.return_value = (
            self.covered, self.uncovered, uuid.uuid4(),
        )
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "COVERAGE_INCOMPLETE")
        self.repo.create_active.assert_not_called()

    def test_unapproved_or_drifted_prototype_fails_closed(self):
        self.reader.get.return_value.version_state = "DRAFT"
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "PROTOTYPE_INPUT_DRIFT")
        self.reader.get.return_value.version_state = "APPROVED"
        self.validator.current_facts.return_value = None
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "PROTOTYPE_INPUT_DRIFT")

    def test_missing_owned_requirement_ref_is_hidden(self):
        self.reader.get.return_value.requirement_refs = ()
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_natural_duplicate_with_different_payload_conflicts(self):
        self.repo.create_active.return_value = StoredRequirementPrototypeLink(
            self.link, False,
        )
        self.repo.get.return_value = RequirementPrototypeLinkView(
            self.link, self.project, self.requirement, uuid.uuid4(),
            self.prototype, self.prototype_version, "ILLUSTRATES",
            self.coverage, "ACTIVE", 0, self.actor, self.now, None,
        )
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command())
        self.assertEqual(caught.exception.code, "LINK_CONFLICT")
        self.audit.append.assert_not_called()

    def test_list_is_authorized_and_stably_paged(self):
        older = RequirementPrototypeLinkView(
            uuid.uuid4(), self.project, self.requirement,
            self.requirement_version, self.prototype, self.prototype_version,
            "VALIDATES", self.coverage, "REVOKED", 1, self.actor,
            self.now, None,
        )
        self.repo.list_links.return_value = (self.view, older)
        page = self.service.list(RequirementPrototypeLinkQuery(
            b"s" * 32, uuid.uuid4(), self.project,
        ), page_size=1)
        self.assertEqual(page.items, (self.view,))
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_link_id, self.link)
        self.authorization.require_in_transaction.assert_called_with(
            self.tx, user_id=self.actor, project_id=self.project,
            operation="PRT_LINK_LIST",
        )

    def test_invalid_coverage_and_secrets_are_rejected(self):
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.create(self.command(RequirementPrototypeCoverage((), ())))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        rendered = repr(self.command())
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)

    def test_revoke_is_atomic_audited_and_replayable(self):
        revoked = RequirementPrototypeLinkView(
            self.link, self.project, self.requirement, self.requirement_version,
            self.prototype, self.prototype_version, "ILLUSTRATES",
            self.coverage, "REVOKED", 1, self.actor, self.now, None,
        )
        self.repo.get.return_value = revoked
        command = RevokeRequirementPrototypeLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.link, 0, str(uuid.uuid4()),
        )
        self.assertEqual(self.service.revoke(command), revoked)
        self.repo.revoke_active.assert_called_once_with(
            self.tx, project_id=self.project, link_id=self.link,
        )
        self.assertEqual(
            self.audit.append.call_args.args[1].action,
            "REQUIREMENT_PROTOTYPE_LINK_REVOKED",
        )
        result = self.receipts.complete.call_args.kwargs["result"]
        self.assertEqual((result.ref_id, result.status_code), (self.link, 200))

    def test_supersede_terminates_old_before_inserting_replacement(self):
        replacement_id = uuid.uuid4()
        replacement_coverage = RequirementPrototypeCoverage(
            (self.covered,),
            (UncoveredAcceptanceCriterion(self.uncovered, "Deferred"),),
        )
        replacement = RequirementPrototypeLinkView(
            replacement_id, self.project, self.requirement,
            self.requirement_version, self.prototype, self.prototype_version,
            "ILLUSTRATES", replacement_coverage, "ACTIVE", 0, self.actor,
            self.now, None,
        )
        self.repo.get.return_value = replacement
        self.repo.replacement_matches.return_value = True
        order = Mock()
        order.attach_mock(self.repo.supersede_active, "terminate_old")
        order.attach_mock(self.repo.create_replacement, "insert_new")
        result = self.service.supersede(SupersedeRequirementPrototypeLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.link,
            self.requirement, self.requirement_version, self.prototype,
            self.prototype_version, "ILLUSTRATES", replacement_coverage,
            0, str(uuid.uuid4()),
        ))
        self.assertEqual(result, replacement)
        self.assertEqual(
            [call[0] for call in order.mock_calls],
            ["terminate_old", "insert_new"],
        )
        self.assertEqual(self.audit.append.call_count, 2)
        self.assertEqual(
            self.receipts.complete.call_args.kwargs["result"].status_code, 201,
        )

    def test_supersede_rejects_identity_purpose_or_unchanged_payload(self):
        for field, value in (
            ("requirement_id", uuid.uuid4()),
            ("prototype_id", uuid.uuid4()),
            ("purpose", "VALIDATES"),
        ):
            data = dict(
                session_token=b"s" * 32, csrf_token=b"c" * 32,
                trace_id=uuid.uuid4(), project_id=self.project,
                requirement_prototype_link_id=self.link,
                requirement_id=self.requirement,
                requirement_version_id=self.requirement_version,
                prototype_id=self.prototype,
                prototype_version_id=self.prototype_version,
                purpose="ILLUSTRATES", coverage=self.coverage,
                expected_version=0, idempotency_key=str(uuid.uuid4()),
            )
            data[field] = value
            with self.assertRaises(RequirementPrototypeLinkError) as caught:
                self.service.supersede(SupersedeRequirementPrototypeLink(**data))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.repo.supersede_active.assert_not_called()

    def test_lifecycle_replay_checks_terminal_chain(self):
        replacement_id = uuid.uuid4()
        replacement_coverage = RequirementPrototypeCoverage(
            (self.uncovered,),
            (UncoveredAcceptanceCriterion(self.covered, "Alternative"),),
        )
        replacement = RequirementPrototypeLinkView(
            replacement_id, self.project, self.requirement,
            self.requirement_version, self.prototype, self.prototype_version,
            "ILLUSTRATES", replacement_coverage, "ACTIVE", 0, self.actor,
            self.now, None,
        )
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_PRT_REQUIREMENT_LINK_REPLACEMENT", replacement_id, 201,
        )
        self.repo.get.return_value = replacement
        self.repo.replacement_matches.return_value = True
        result = self.service.supersede(SupersedeRequirementPrototypeLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.link,
            self.requirement, self.requirement_version, self.prototype,
            self.prototype_version, "ILLUSTRATES", replacement_coverage,
            0, str(uuid.uuid4()),
        ))
        self.assertEqual(result, replacement)
        self.repo.lock_active.assert_not_called()
        self.repo.create_replacement.assert_not_called()
        self.validator.current_facts.assert_called_once()

    def test_lifecycle_requires_initial_strong_version(self):
        with self.assertRaises(RequirementPrototypeLinkError) as caught:
            self.service.revoke(RevokeRequirementPrototypeLink(
                b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
                self.link, 1, str(uuid.uuid4()),
            ))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
