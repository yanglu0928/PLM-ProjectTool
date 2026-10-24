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
from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import (
    PromptAdmissionError, SignedPromptAdmission,
)


def sign(payload: dict, private_key: Ed25519PrivateKey) -> bytes:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode()
    signature = private_key.sign(b"PLM-PROMPT-ADMISSION-V1\n" + canonical)
    return json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                       "signature": base64.b64encode(signature).decode()},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class SignedPromptAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.draft = PromptVersionDraft(
            uuid.uuid4(), PromptTaskType.GAP_ANALYSIS,
            "Synthetic system {context}", "Synthetic user {input}",
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
        )
        self.entry = {"prompt_template_id": str(self.draft.prompt_template_id),
                      "task_type": self.draft.task_type.value,
                      "fingerprint": self.draft.fingerprint.hex()}
        self.payload = {"generation": 1, "reviewer_ref": "developer.synthetic",
                        "reviewed_at": "2026-10-02T00:00:00Z", "entries": [self.entry]}

    def verifier(self, payload: dict | None = None) -> SignedPromptAdmission:
        document = sign(payload or self.payload, self.private)
        return SignedPromptAdmission(
            public_key=self.public, signed_manifest=document,
            expected_manifest_sha256=hashlib.sha256(document).digest(),
        )

    def test_exact_signed_candidate_only(self) -> None:
        verifier = self.verifier()
        self.assertEqual(verifier.approved_fingerprint(object(), actor_id=uuid.uuid4(),
                                                       draft=self.draft), self.draft.fingerprint)
        for altered in (
            replace(self.draft, prompt_template_id=uuid.uuid4()),
            replace(self.draft, task_type=PromptTaskType.SURVEY_GENERATE),
            replace(self.draft, user_template="Changed {input}"),
            replace(self.draft, schema_version=2),
        ):
            self.assertIsNone(verifier.approved_fingerprint(object(), actor_id=uuid.uuid4(),
                                                             draft=altered))
        self.assertIsNone(verifier.approved_fingerprint(None, actor_id=uuid.uuid4(), draft=self.draft))

    def test_signature_digest_and_trust_fail_closed(self) -> None:
        document = sign(self.payload, self.private)
        digest = hashlib.sha256(document).digest()
        with self.assertRaises(PromptAdmissionError):
            SignedPromptAdmission(public_key=self.public, signed_manifest=document,
                                  expected_manifest_sha256=b"x" * 32)
        with self.assertRaises(PromptAdmissionError):
            SignedPromptAdmission(public_key=b"x" * 32, signed_manifest=document,
                                  expected_manifest_sha256=digest)
        tampered = document.replace(b"developer.synthetic", b"developer.tampered")
        with self.assertRaises(PromptAdmissionError):
            SignedPromptAdmission(public_key=self.public, signed_manifest=tampered,
                                  expected_manifest_sha256=hashlib.sha256(tampered).digest())

    def test_reject_malformed_and_ambiguous_manifest(self) -> None:
        duplicate = (b'{"format":"PLM_PROMPT_ADMISSION_V1","format":"PLM_PROMPT_ADMISSION_V1",'
                     b'"payload":{},"signature":""}')
        with self.assertRaises(PromptAdmissionError):
            SignedPromptAdmission(public_key=self.public, signed_manifest=duplicate,
                                  expected_manifest_sha256=hashlib.sha256(duplicate).digest())
        for payload in (
            {**self.payload, "entries": []},
            {**self.payload, "entries": [self.entry, self.entry]},
            {**self.payload, "entries": [{**self.entry, "extra": "no"}]},
            {**self.payload, "generation": True},
            {**self.payload, "reviewed_at": "not-a-date"},
            {**self.payload, "entries": [
                {**self.entry, "prompt_template_id": "ffffffff-ffff-4fff-8fff-ffffffffffff"},
                self.entry,
            ]},
        ):
            with self.subTest(payload=payload), self.assertRaises(PromptAdmissionError):
                self.verifier(payload)

    def test_reject_oversize_encoding_and_bad_signature_length(self) -> None:
        for document in (
            b"x" * 65_537, b"\xff",
            json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": self.payload,
                        "signature": "not-base64!"}).encode(),
        ):
            with self.subTest(size=len(document)), self.assertRaises(PromptAdmissionError):
                SignedPromptAdmission(
                    public_key=self.public, signed_manifest=document,
                    expected_manifest_sha256=hashlib.sha256(document).digest(),
                )


if __name__ == "__main__":
    unittest.main()
