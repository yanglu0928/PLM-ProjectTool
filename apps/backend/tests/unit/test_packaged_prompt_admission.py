from __future__ import annotations

import base64
import hashlib
import json
import unittest
import uuid
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.packaged_prompt_admission import (
    PackagedPromptAdmission, PackagedPromptAdmissionError,
)


def _signed(payload: dict, private: Ed25519PrivateKey) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    signature = private.sign(b"PLM-PROMPT-ADMISSION-V1\n" + canonical)
    return json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                       "signature": base64.b64encode(signature).decode("ascii")},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


class PackagedPromptAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        self.draft = PromptVersionDraft(
            uuid.uuid4(), PromptTaskType.GAP_ANALYSIS,
            "Synthetic system {context}", "Synthetic user {input}",
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
        )
        self.payload = {"generation": 7, "reviewer_ref": "developer.synthetic",
                        "reviewed_at": "2026-10-02T00:00:00Z",
                        "entries": [{"prompt_template_id": str(self.draft.prompt_template_id),
                                     "task_type": self.draft.task_type.value,
                                     "fingerprint": self.draft.fingerprint.hex()}]}
        self.signed = _signed(self.payload, self.private)
        self.release = {"schema_version": "plm.prompt-admission-release.v1",
                        "key_ref": "plm-prompt-admission-release-v1",
                        "public_key": base64.b64encode(public).decode("ascii"),
                        "manifest_sha256": hashlib.sha256(self.signed).hexdigest(),
                        "generation": 7}

    def load(self, release: dict | bytes | None = None, signed: bytes | None = None) -> PackagedPromptAdmission:
        raw = json.dumps(self.release if release is None else release,
                         separators=(",", ":")).encode() if not isinstance(release, bytes) else release
        return PackagedPromptAdmission(read_release=lambda: raw,
                                       read_signed_manifest=lambda: self.signed if signed is None else signed)

    def test_exact_candidate_only(self) -> None:
        admission = self.load()
        self.assertEqual(admission.approved_fingerprint(
            object(), actor_id=uuid.uuid4(), draft=self.draft,
        ), self.draft.fingerprint)
        self.assertIsNone(admission.approved_fingerprint(
            object(), actor_id=uuid.uuid4(),
            draft=replace(self.draft, user_template="Changed {input}"),
        ))

    def test_tamper_key_generation_and_invalid_release_fail_closed(self) -> None:
        for release, signed in (
            ({**self.release, "manifest_sha256": "0" * 64}, None),
            ({**self.release, "generation": 6}, None),
            ({**self.release, "key_ref": "plm-project-tool-release-v1"}, None),
            ({**self.release, "public_key": base64.b64encode(b"x" * 32).decode()}, None),
            ({**self.release, "extra": "no"}, None),
            ({**self.release, "generation": True}, None),
            (self.release, self.signed.replace(b"developer.synthetic", b"developer.tampered")),
        ):
            with self.subTest(release=release, signed=signed), self.assertRaises(PackagedPromptAdmissionError):
                self.load(release, signed)
        duplicate = b'{"schema_version":"plm.prompt-admission-release.v1","schema_version":"x"}'
        with self.assertRaises(PackagedPromptAdmissionError):
            self.load(duplicate)

    def test_missing_packaged_resources_fail_closed(self) -> None:
        # No formal trust files are shipped in the development wheel yet.
        with self.assertRaises(PackagedPromptAdmissionError):
            PackagedPromptAdmission()


if __name__ == "__main__":
    unittest.main()
