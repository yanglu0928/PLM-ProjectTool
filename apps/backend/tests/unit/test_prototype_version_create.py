from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.prototype.application.create_version import (
    CreatePrototypeVersion, PrototypeVersionCreateError,
    PrototypeVersionCreateService, PrototypeVersionInitialView,
    VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class Access:
    actor = uuid.uuid4()
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Authorization:
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        return SimpleNamespace(user_id=user_id, project_id=project_id, operation=operation)


class Guard:
    def require_valid(self, **_kwargs): return object()


class Requirements:
    def prove(self, _tx, *, project_id, requirement_id, requirement_version_id):
        return PrototypeApprovedRequirementVersionProof(
            project_id, requirement_id, requirement_version_id, 1, "1" * 64,
            uuid.uuid4(), uuid.uuid4())


class Templates:
    def prove(self, _tx, *, project_id, prototype_template_id,
              prototype_template_version_id):
        return PrototypeVersionTemplateProof(
            prototype_template_id, prototype_template_version_id, "PROJECT",
            project_id, 1, "2" * 64)


class Documents:
    def prove_for_prototype_version(self, _tx, *, project_id, document_version_id):
        return PrototypeVersionDocumentArtifactProof(
            document_version_id, uuid.uuid4(), "PROJECT", project_id,
            "3" * 64, 10, "application/pdf")


class Receipts:
    previous = None
    def reserve(self, *_args, **_kwargs): return self.previous
    def complete(self, _tx, *, scope, result): self.previous = result


class Audit:
    def append(self, *_args, **_kwargs): self.called = True


class Repository:
    def __init__(self): self.view = None
    def create(self, _tx, **values):
        self.view = PrototypeVersionInitialView(
            values["version_id"], values["prototype_id"], values["project_id"],
            1, None, values["template_id"], values["template_version_id"],
            values["artifacts"], values["requirements"], values["interaction"],
            values["coverage"], values["content_fingerprint"].hex(), NOW)
        return self.view
    def result(self, _tx, **_kwargs): return self.view


class PrototypeVersionCreateTests(unittest.TestCase):
    def setUp(self):
        self.project, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.template, self.template_version = uuid.uuid4(), uuid.uuid4()
        self.document = uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.repository, self.receipts = Repository(), Receipts()
        self.service = PrototypeVersionCreateService(
            unit_of_work=Tx, project_access=Access(), license_guard=Guard(),
            authorization=Authorization(), requirements=Requirements(),
            templates=Templates(), documents=Documents(), repository=self.repository,
            receipts=self.receipts, audit=Audit(), clock=lambda: NOW)

    def command(self, *, kind="DOCUMENT_VERSION"):
        return CreatePrototypeVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.prototype,
            self.template, self.template_version,
            (VersionArtifactRef(kind, self.document),),
            (VersionRequirementRef(self.requirement, self.requirement_version),),
            {"interactions": []}, {"covered": 1}, "version-key-123456")

    def test_create_and_persistent_replay_return_same_draft(self):
        first = self.service.create(self.command())
        second = self.service.create(self.command())
        self.assertEqual(first, second)
        self.assertEqual(first.version_state, "DRAFT")
        self.assertIsNone(first.supersedes_version_id)

    def test_output_artifact_fails_closed_without_owner(self):
        with self.assertRaisesRegex(PrototypeVersionCreateError,
                                    "PROTOTYPE_ARTIFACT_UNAVAILABLE"):
            self.service.create(self.command(kind="OUTPUT_ARTIFACT"))

    def test_empty_owned_sets_and_executable_interaction_are_rejected(self):
        command = self.command()
        with self.assertRaisesRegex(PrototypeVersionCreateError, "VALIDATION_FAILED"):
            self.service.create(CreatePrototypeVersion(
                command.session_token, command.csrf_token, command.trace_id,
                command.project_id, command.prototype_id, command.template_id,
                command.template_version_id, (), command.requirement_refs,
                command.interaction_spec, command.coverage_summary,
                command.idempotency_key))
        with self.assertRaisesRegex(PrototypeVersionCreateError, "VALIDATION_FAILED"):
            self.service.create(CreatePrototypeVersion(
                command.session_token, command.csrf_token, command.trace_id,
                command.project_id, command.prototype_id, command.template_id,
                command.template_version_id, command.artifact_refs,
                command.requirement_refs, {"script": "powershell"},
                command.coverage_summary, command.idempotency_key))


if __name__ == "__main__": unittest.main()
