from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.prototype.application.approval_trace import (
    PrototypeApprovalTraceError,
    PrototypeApprovalTraceOwner,
)
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView,
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.current_version import (
    PrototypeVersionCurrentFacts,
)
from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.trace.application.create_link import StoredTraceLink


class PrototypeApprovalTraceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.project, self.prototype, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.template, self.template_version = uuid.uuid4(), uuid.uuid4()
        self.document, self.document_version = uuid.uuid4(), uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.snapshot = PrototypeVersionInitialView(
            self.version, self.prototype, self.project, 1, None,
            self.template, self.template_version,
            (VersionArtifactRef("DOCUMENT_VERSION", self.document_version),),
            (VersionRequirementRef(
                self.requirement, self.requirement_version),),
            {"interactions": []}, {"covered": 1}, "1" * 64,
            datetime(2026, 10, 8, tzinfo=timezone.utc),
        )
        self.facts = PrototypeVersionCurrentFacts(
            PrototypeVersionTemplateProof(
                self.template, self.template_version, "GLOBAL", None,
                1, "2" * 64,
            ),
            (PrototypeVersionDocumentArtifactProof(
                self.document_version, self.document, "PROJECT", self.project,
                "3" * 64, 10, "application/pdf",
            ),),
            (PrototypeApprovedRequirementVersionProof(
                self.project, self.requirement, self.requirement_version,
                1, "4" * 64, uuid.uuid4(), uuid.uuid4(),
            ),),
        )
        self.current, self.links, self.manifests = (Mock() for _ in range(3))
        self.current.current_facts.return_value = self.facts
        self.link_ids = tuple(uuid.uuid4() for _ in range(3))
        self.links.create_active.side_effect = tuple(
            StoredTraceLink(link_id, True) for link_id in self.link_ids)
        self.owner = PrototypeApprovalTraceOwner(
            current=self.current, trace_links=self.links,
            manifests=self.manifests,
        )
        self.result, self.review, self.round = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.actor, self.trace_id = uuid.uuid4(), uuid.uuid4()
        self.tx = object()

    def test_records_exact_ordered_business_version_edges_and_manifest(self):
        self.owner.record_in_transaction(
            self.tx, snapshot=self.snapshot,
            review_state_result_id=self.result, review_id=self.review,
            review_round_id=self.round, actor_id=self.actor,
            trace_id=self.trace_id,
        )
        calls = self.links.create_active.call_args_list
        self.assertEqual(len(calls), 3)
        edges = [call.kwargs["edge"] for call in calls]
        self.assertEqual(
            [(edge.source.owner_module, edge.source.object_type,
              edge.relation_type) for edge in edges],
            [
                ("prototype", "PRT-04", "DERIVED_FROM"),
                ("document", "DOC-02", "DERIVED_FROM"),
                ("requirement", "REQ-03", "IMPLEMENTS"),
            ],
        )
        self.assertTrue(all(
            edge.target.owner_module == "prototype"
            and edge.target.object_type == "PRT-03"
            and edge.target.object_id == self.prototype
            and edge.target.version_id == self.version
            and edge.target.project_id == self.project
            for edge in edges
        ))
        manifest = self.manifests.insert_manifest.call_args.kwargs["manifest"]
        self.assertEqual(manifest.review_state_result_id, self.result)
        self.assertEqual(
            tuple(item.trace_link_id for item in manifest.sources),
            self.link_ids,
        )
        self.assertEqual(
            tuple(item.ordinal for item in manifest.sources), (1, 2, 3),
        )

    def test_fails_closed_before_manifest_on_current_or_trace_error(self):
        self.current.current_facts.return_value = None
        with self.assertRaises(PrototypeApprovalTraceError):
            self._record()
        self.links.create_active.assert_not_called()
        self.manifests.insert_manifest.assert_not_called()

        self.current.current_facts.return_value = self.facts
        self.links.create_active.side_effect = ValueError("unsafe detail")
        with self.assertRaisesRegex(PrototypeApprovalTraceError, "^$"):
            self._record()
        self.manifests.insert_manifest.assert_not_called()

    def test_replay_requires_exact_manifest_projection(self):
        self.manifests.manifest_matches.return_value = True
        self.owner.assert_recorded_in_transaction(
            self.tx, prototype_version_id=self.version,
            prototype_id=self.prototype, project_id=self.project,
            review_state_result_id=self.result, review_id=self.review,
            review_round_id=self.round, actor_id=self.actor,
        )
        self.manifests.manifest_matches.return_value = False
        with self.assertRaises(PrototypeApprovalTraceError):
            self.owner.assert_recorded_in_transaction(
                self.tx, prototype_version_id=self.version,
                prototype_id=self.prototype, project_id=self.project,
                review_state_result_id=self.result, review_id=self.review,
                review_round_id=self.round, actor_id=self.actor,
            )

    def _record(self):
        return self.owner.record_in_transaction(
            self.tx, snapshot=self.snapshot,
            review_state_result_id=self.result, review_id=self.review,
            review_round_id=self.round, actor_id=self.actor,
            trace_id=self.trace_id,
        )


if __name__ == "__main__":
    unittest.main()
