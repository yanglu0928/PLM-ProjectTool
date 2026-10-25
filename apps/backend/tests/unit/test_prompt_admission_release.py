from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.packaged_prompt_admission import PackagedPromptAdmission


_SCRIPT = Path(__file__).resolve().parents[4] / "tools/developer-workbench/prompt_admission_release.py"
_SPEC = importlib.util.spec_from_file_location("prompt_admission_release_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


class PromptAdmissionReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        self.public = json.dumps({
            "schema_version": "plm.prompt-admission-public-key.v1",
            "key_ref": "plm-prompt-admission-release-v1",
            "public_key": base64.b64encode(public).decode("ascii"),
        }).encode()
        self.draft = PromptVersionDraft(
            uuid.uuid4(), PromptTaskType.GAP_ANALYSIS,
            "Synthetic system {context}", "Synthetic user {input}",
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
        )
        payload = {"generation": 4, "reviewer_ref": "developer.synthetic",
                   "reviewed_at": "2026-10-02T00:00:00Z",
                   "entries": [{"prompt_template_id": str(self.draft.prompt_template_id),
                                "task_type": self.draft.task_type.value,
                                "fingerprint": self.draft.fingerprint.hex()}]}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode()
        self.signed = json.dumps({
            "format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
            "signature": base64.b64encode(
                private.sign(b"PLM-PROMPT-ADMISSION-V1\n" + canonical),
            ).decode("ascii"),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    def test_prepare_interoperates_with_packaged_loader(self) -> None:
        release = builder.prepare_release(self.public, self.signed)
        metadata = json.loads(release)
        self.assertEqual(metadata["generation"], 4)
        self.assertEqual(metadata["manifest_sha256"], hashlib.sha256(self.signed).hexdigest())
        admission = PackagedPromptAdmission(read_release=lambda: release,
                                            read_signed_manifest=lambda: self.signed)
        self.assertEqual(admission.approved_fingerprint(
            object(), actor_id=uuid.uuid4(), draft=self.draft,
        ), self.draft.fingerprint)

    def test_wrong_key_tamper_duplicate_and_invalid_public_rejected(self) -> None:
        bad_key = json.loads(self.public)
        bad_key["public_key"] = base64.b64encode(b"x" * 32).decode()
        for public, signed in (
            (json.dumps(bad_key).encode(), self.signed),
            (self.public, self.signed.replace(b"developer.synthetic", b"developer.tampered")),
            (b'{"schema_version":"plm.prompt-admission-public-key.v1","schema_version":"x"}', self.signed),
            (b"\xff", self.signed),
            (self.public, b"x" * 65_537),
        ):
            with self.subTest(public=public[:20]), self.assertRaises(builder.PromptReleaseError):
                builder.prepare_release(public, signed)

    def test_cli_exclusive_write_and_no_private_material(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            public, signed, output = (base / "public.json", base / "signed.json",
                                      base / "release.json")
            public.write_bytes(self.public)
            signed.write_bytes(self.signed)
            with (mock.patch.object(builder.sys, "argv", ["prompt_admission_release.py", "prepare",
                                                         str(public), str(signed), str(output)]),
                  mock.patch.object(builder.sys, "stdout", io.StringIO()),
                  mock.patch.object(builder.sys, "stderr", io.StringIO())):
                self.assertEqual(builder.main(), 0)
                previous = output.read_bytes()
                self.assertEqual(builder.main(), 1)
                self.assertEqual(output.read_bytes(), previous)
            self.assertNotIn(b"Synthetic system", previous)
            self.assertNotIn(b"PRIVATE KEY", previous)


if __name__ == "__main__":
    unittest.main()
