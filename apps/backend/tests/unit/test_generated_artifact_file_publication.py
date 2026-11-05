from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.document.application.generated_artifact_file import (
    GeneratedFilePublicationError, GeneratedFileRequestFacts,
    GeneratedFileSnapshot, OutputGeneratedFilePublicationOwner,
)
from plm_assistant.modules.document.infrastructure.local_storage import FileContentProof
from plm_assistant.modules.output.application.complete_generation import (
    OutputArtifactPublication, OutputValidationEvidence,
)


class _Storage:
    def __init__(self, shape):
        self.shape, self.calls = shape, []

    def inspect_recovery(self, *args, **kwargs):
        self.calls.append("inspect")
        return type("Inspection", (), {"shape": self.shape})()

    def _proof(self, locator, **kwargs):
        self.calls.append(locator)
        return FileContentProof(locator, kwargs["expected_sha256"], kwargs["expected_size"])

    def publish_verified(self, locator, *args, **kwargs):
        self.calls.append("publish_verified")
        return self._proof(locator, **kwargs)

    def recover_verified_final(self, staging, final, *args, **kwargs):
        self.calls.append("recover_verified_final")
        return self._proof(final, **kwargs)

    def recover_linked_pair(self, staging, final, *args, **kwargs):
        self.calls.append("recover_linked_pair")
        return self._proof(final, **kwargs)

    def verify_content(self, locator, **kwargs):
        return self._proof(locator, **kwargs)


class GeneratedFileRecoveryDispatchTests(unittest.TestCase):
    def setUp(self):
        self.project_id, self.document_id, self.file_id = (uuid.uuid4() for _ in range(3))
        self.digest = b"d" * 32
        self.publication = OutputArtifactPublication(
            artifact_id=uuid.uuid4(), plugin_execution_id=uuid.uuid4(),
            document_id=self.document_id, document_version_id=uuid.uuid4(),
            file_object_id=self.file_id, sha256=self.digest, size_bytes=17,
            media_type="image/png", validations=(
                OutputValidationEvidence("FORMAT_CHECK", "PASSED"),
                OutputValidationEvidence("STRUCTURE_CHECK", "PASSED"),
                OutputValidationEvidence("HASH_CHECK", "PASSED", self.digest),
                OutputValidationEvidence("CONTENT_CHECK", "PASSED"),
            ),
        )
        request = GeneratedFileRequestFacts(
            output_request_id=uuid.uuid4(), project_id=self.project_id,
            job_id=uuid.uuid4(), execution_id=self.publication.plugin_execution_id,
            requested_by=uuid.uuid4(), trace_id=uuid.uuid4(),
            request_state="GENERATING", request_lock_version=1,
        )
        self.snapshot = GeneratedFileSnapshot(
            request=request, document_id=self.document_id, file_object_id=self.file_id,
            file_state="STAGED", file_lock_version=1, storage_locator="stage",
            staging_locator="stage", final_locator="final", sha256=self.digest,
            size_bytes=17, media_type="image/png",
        )

    def owner(self, storage):
        return OutputGeneratedFilePublicationOwner(
            unit_of_work=object(), jobs=object(), repository=object(), storage=storage,
            audit=object(), version_owner=object(), completion_owner=object(),
            system_actor_id=uuid.uuid4(),
        )

    def test_safe_recovery_shapes_dispatch_to_exact_storage_operation(self):
        cases = {
            "STAGE_ONLY": ("publish_verified", ["inspect", "publish_verified", "final"]),
            "FINAL_VERIFIED": ("recover_verified_final", ["inspect", "recover_verified_final", "final"]),
            "LINKED_PAIR": ("recover_linked_pair", ["inspect", "recover_linked_pair", "final"]),
        }
        for shape, (_, expected_calls) in cases.items():
            with self.subTest(shape=shape):
                storage = _Storage(shape)
                proof = self.owner(storage)._prove_and_promote(self.snapshot, self.publication)
                self.assertEqual(proof.locator, "final")
                self.assertIn(shape.lower(), expected_calls[1])
                self.assertEqual(storage.calls, expected_calls)

    def test_unknown_unrelated_and_unsafe_shapes_fail_closed(self):
        for shape in ("NONE", "BOTH_UNRELATED", "FINAL_INVALID", "UNSAFE", "UNKNOWN"):
            with self.subTest(shape=shape):
                storage = _Storage(shape)
                with self.assertRaises(GeneratedFilePublicationError):
                    self.owner(storage)._prove_and_promote(self.snapshot, self.publication)
                self.assertEqual(storage.calls, ["inspect"])

    def test_available_final_only_verifies_content(self):
        storage = _Storage("UNSAFE")
        snapshot = GeneratedFileSnapshot(
            request=self.snapshot.request, document_id=self.document_id,
            file_object_id=self.file_id, file_state="AVAILABLE", file_lock_version=2,
            storage_locator="final", staging_locator="stage", final_locator="final",
            sha256=self.digest, size_bytes=17, media_type="image/png",
        )
        proof = self.owner(storage)._prove_and_promote(snapshot, self.publication)
        self.assertEqual(proof, FileContentProof("final", self.digest, 17))
        self.assertEqual(storage.calls, ["final"])

    def test_locator_state_mismatch_fails_before_storage_access(self):
        storage = _Storage("STAGE_ONLY")
        snapshot = GeneratedFileSnapshot(
            request=self.snapshot.request, document_id=self.document_id,
            file_object_id=self.file_id, file_state="STAGED", file_lock_version=1,
            storage_locator="final", staging_locator="stage", final_locator="final",
            sha256=self.digest, size_bytes=17, media_type="image/png",
        )
        with self.assertRaises(GeneratedFilePublicationError):
            self.owner(storage)._prove_and_promote(snapshot, self.publication)
        self.assertEqual(storage.calls, [])

    def test_available_file_cannot_resolve_to_staging(self):
        storage = _Storage("UNSAFE")
        snapshot = GeneratedFileSnapshot(
            request=self.snapshot.request, document_id=self.document_id,
            file_object_id=self.file_id, file_state="AVAILABLE", file_lock_version=2,
            storage_locator="stage", staging_locator="stage", final_locator="final",
            sha256=self.digest, size_bytes=17, media_type="image/png",
        )
        with self.assertRaises(GeneratedFilePublicationError):
            self.owner(storage)._prove_and_promote(snapshot, self.publication)
        self.assertEqual(storage.calls, [])


if __name__ == "__main__":
    unittest.main()
