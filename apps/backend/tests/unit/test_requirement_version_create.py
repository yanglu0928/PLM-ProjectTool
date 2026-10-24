from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.capability.application.requirement_source_proof import (
    CapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, CreatedRequirementVersion,
    RequirementAcceptanceDraft, RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
    RequirementVersionCreateError, RequirementVersionCreateService,
    RequirementVersionRootLock,
)


class Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class Repo:
    def __init__(self, command):
        self.command = command
        self.root = RequirementVersionRootLock(
            command.requirement_id, command.project_id, "ACTIVE",
            command.expected_lock_version, 0, None,
        )
        self.created = None
    def lock_requirement(self, *_args, **_kwargs): return self.root
    def create(self, _tx, *, root, requirement_version_id, actor_id,
               content_fingerprint, command):
        self.created = CreatedRequirementVersion(
            requirement_version_id, root.requirement_id, root.project_id,
            root.highest_version_no + 1, "DRAFT", content_fingerprint,
            root.latest_version_id, actor_id, datetime.now(timezone.utc),
            root.lock_version, root.lock_version + 1,
        )
        return self.created
    def initial_view(self, *_args, **_kwargs): return self.created


class RequirementVersionCreateTests(unittest.TestCase):
    def setUp(self):
        self.project, self.requirement = uuid.uuid4(), uuid.uuid4()
        self.actor, self.evidence = uuid.uuid4(), uuid.uuid4()
        self.global_evidence, self.baseline, self.item = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.command = CreateRequirementVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.requirement, 0, True, None, None,
            "The system shall export an approved package.",
            "Required for controlled delivery.", "OUTPUT", "HIGH", "MEDIUM",
            "STANDARD_FUNCTION",
            (RequirementSourceDraft(
                "PROJECT_EVIDENCE", self.evidence, None, (self.evidence,),
            ),),
            (RequirementAcceptanceDraft(
                "An approved package is produced", "Run release validation",
                "Approved project", "Windows 11", "Release report",
            ),),
            (RequirementCapabilityAssessmentDraft(
                self.baseline, self.item, "DIRECT", "No fit gap", "Licensed use",
                "HUMAN", "CONFIRMED", (
                    RequirementAssessmentEvidenceDraft(
                        self.global_evidence, "STANDARD"),
                    RequirementAssessmentEvidenceDraft(self.evidence, "PROJECT"),
                ),
            ),),
            (), (), (), (), "Create controlled draft", str(uuid.uuid4()),
        )
        self.tx = Tx()
        self.repo = Repo(self.command)
        project_proof = EvidenceRequirementSourceProof(
            self.evidence, self.project, uuid.uuid4(), uuid.uuid4(), 0, b"p" * 32,
        )
        self.project_evidence = SimpleNamespace(
            prove=lambda *_args, **kwargs: project_proof
            if kwargs["evidence_id"] == self.evidence else None)
        global_proof = LockedEvidenceSource(
            self.global_evidence, "GLOBAL", None, uuid.uuid4(), uuid.uuid4(),
            None, {}, b"g" * 32, 0,
        )
        capability = CapabilityRequirementSourceProof(
            self.baseline, uuid.uuid4(), self.item, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), 1, b"k" * 32,
        )
        self.receipts = SimpleNamespace(
            reserve=lambda *_args, **_kwargs: None,
            complete=lambda *_args, **_kwargs: None,
        )
        self.service = RequirementVersionCreateService(
            unit_of_work=lambda: self.tx,
            access=SimpleNamespace(authenticated_user=lambda *_args, **_kwargs: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_kwargs: object()),
            authorization=SimpleNamespace(require_in_transaction=lambda *_args, **_kwargs:
                SimpleNamespace(user_id=self.actor, project_id=self.project,
                                operation="REQ_VERSION_CREATE")),
            repository=self.repo, receipts=self.receipts,
            audit=SimpleNamespace(append=lambda *_args, **_kwargs: uuid.uuid4()),
            survey_sources=object(), handover_sources=object(), human_decisions=object(),
            project_evidence=self.project_evidence,
            capability_sources=SimpleNamespace(prove=lambda *_args, **_kwargs: capability),
            fixed_evidence=SimpleNamespace(get_for_trace=lambda *_args, **kwargs:
                global_proof if kwargs["evidence_id"] == self.global_evidence else None),
        )

    def test_complete_create_commits_draft_and_root_etag(self):
        result = self.service.create(self.command)
        self.assertEqual(result.requirement_id, self.requirement)
        self.assertEqual(result.version_no, 1)
        self.assertEqual(result.lock_version, 1)
        self.assertTrue(self.tx.committed)
        self.assertEqual(len(result.content_fingerprint), 32)

    def test_initial_and_base_are_exclusive(self):
        for command in (
            replace(self.command, initial=False, base_version_ref=None),
            replace(self.command, initial=True, base_version_ref=uuid.uuid4()),
        ):
            with self.assertRaises(RequirementVersionCreateError) as caught:
                self.service.create(command)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_nonempty_ai_provenance_fails_closed(self):
        with self.assertRaises(RequirementVersionCreateError) as caught:
            self.service.create(replace(self.command, ai_task_refs=(uuid.uuid4(),)))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_ai_candidate_assessment_without_atomic_provenance_fails_closed(self):
        candidate = replace(
            self.command.capability_assessments[0],
            assessor_kind="AI_CANDIDATE", confirmation_state="CANDIDATE",
        )
        with self.assertRaises(RequirementVersionCreateError) as caught:
            self.service.create(replace(
                self.command, capability_assessments=(candidate,),
            ))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_stale_base_is_rejected_after_lock(self):
        self.repo.root = RequirementVersionRootLock(
            self.requirement, self.project, "ACTIVE", 4, 1, uuid.uuid4())
        command = replace(self.command, expected_lock_version=4, initial=False,
                          base_version_ref=uuid.uuid4())
        with self.assertRaises(RequirementVersionCreateError) as caught:
            self.service.create(command)
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")

    def test_project_evidence_must_be_current(self):
        self.service._project_evidence = SimpleNamespace(prove=lambda *_a, **_k: None)
        with self.assertRaises(RequirementVersionCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "REQUIREMENT_SOURCE_UNAVAILABLE")

    def test_secrets_and_idempotency_key_are_redacted(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
