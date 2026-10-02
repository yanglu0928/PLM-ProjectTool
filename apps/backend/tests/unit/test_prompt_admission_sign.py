from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import SignedPromptAdmission


_SCRIPT = Path(__file__).resolve().parents[4] / "tools/developer-workbench/prompt_admission_sign.py"
_SPEC = importlib.util.spec_from_file_location("prompt_admission_sign_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
signer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(signer)
_PASSWORD = b"synthetic-only-prompt-passphrase-32"


class PromptAdmissionSignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.draft = PromptVersionDraft(
            uuid.uuid4(), PromptTaskType.GAP_ANALYSIS,
            "Synthetic system {context}", "Synthetic user {input}",
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
        )
        self.candidate = json.dumps({"drafts": [{
            "prompt_template_id": str(self.draft.prompt_template_id),
            "task_type": self.draft.task_type.value,
            "system_template": self.draft.system_template,
            "user_template": self.draft.user_template,
            "output_schema_ref": self.draft.output_schema_ref,
            "schema_version": self.draft.schema_version,
            "rag_policy_ref": self.draft.rag_policy_ref,
            "provider_policy_ref": self.draft.provider_policy_ref,
        }]}, ensure_ascii=False).encode()
        self.private = Ed25519PrivateKey.generate()
        self.pem = self.private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(_PASSWORD),
        )
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )

    def sign(self, candidate: bytes | None = None, digest: str | None = None) -> bytes:
        value = self.candidate if candidate is None else candidate
        return signer.sign_reviewed_candidate(
            value, private_pem=self.pem, passphrase=bytearray(_PASSWORD),
            reviewer_ref="developer.synthetic", generation=1,
            reviewed_at="2026-10-02T00:00:00Z",
            confirmed_candidate_sha256=hashlib.sha256(value).hexdigest() if digest is None else digest,
        )

    def test_signed_output_interoperates_with_runtime_and_exact_draft(self) -> None:
        document = self.sign()
        admission = SignedPromptAdmission(
            public_key=self.public, signed_manifest=document,
            expected_manifest_sha256=hashlib.sha256(document).digest(),
        )
        self.assertEqual(admission.approved_fingerprint(
            object(), actor_id=uuid.uuid4(), draft=self.draft,
        ), self.draft.fingerprint)
        self.assertIsNone(admission.approved_fingerprint(
            object(), actor_id=uuid.uuid4(),
            draft=replace(self.draft, user_template="Different {input}"),
        ))
        self.assertNotIn(b"Synthetic system", document)
        self.assertNotIn(b"Synthetic user", document)

    def test_wrong_confirmation_or_password_fails_and_password_is_cleared(self) -> None:
        password = bytearray(_PASSWORD)
        with self.assertRaises(signer.PromptSigningError):
            signer.sign_reviewed_candidate(
                self.candidate, private_pem=self.pem, passphrase=password,
                reviewer_ref="developer.synthetic", generation=1,
                reviewed_at="2026-10-02T00:00:00Z",
                confirmed_candidate_sha256="0" * 64,
            )
        self.assertEqual(password, bytearray(len(password)))
        password = bytearray(b"wrong-synthetic-passphrase-32")
        with self.assertRaises(signer.PromptSigningError):
            signer.sign_reviewed_candidate(
                self.candidate, private_pem=self.pem, passphrase=password,
                reviewer_ref="developer.synthetic", generation=1,
                reviewed_at="2026-10-02T00:00:00Z",
                confirmed_candidate_sha256=hashlib.sha256(self.candidate).hexdigest(),
            )
        self.assertEqual(password, bytearray(len(password)))

    def test_invalid_candidate_and_manifest_metadata_fail_closed(self) -> None:
        for value in (
            b"\xff", b"{" + b"x" * 1_048_576,
            b'{"drafts":[],"drafts":[]}',
            b'{"drafts":[]}',
            self.candidate.replace(b"system_template", b"fingerprint"),
            self.candidate.replace(b"schema.synthetic.v1", b"sk-" + b"x" * 24),
        ):
            with self.subTest(value=value[:20]), self.assertRaises(signer.PromptSigningError):
                signer.prepare_review(value, reviewer_ref="developer.synthetic", generation=1,
                                      reviewed_at="2026-10-02T00:00:00Z")
        with self.assertRaises(signer.PromptSigningError):
            signer.prepare_review(self.candidate, reviewer_ref="invalid space", generation=1,
                                  reviewed_at="2026-10-02T00:00:00Z")

    def test_duplicate_draft_rejected(self) -> None:
        raw = json.loads(self.candidate)
        raw["drafts"].append(raw["drafts"][0])
        with self.assertRaises(signer.PromptSigningError):
            signer.prepare_review(json.dumps(raw).encode(), reviewer_ref="developer.synthetic",
                                  generation=1, reviewed_at="2026-10-02T00:00:00Z")

    def test_interactive_cli_writes_once_and_rejects_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, private, output = (base / "candidate.json", base / "private.pem",
                                       base / "admission.json")
            source.write_bytes(self.candidate)
            private.write_bytes(self.pem)
            args = ["prompt_admission_sign.py", "sign", str(source), str(private),
                    str(output), "developer.synthetic", "1"]
            with (mock.patch.object(signer.sys, "argv", args),
                  mock.patch.object(signer.sys, "stdin", mock.Mock(isatty=lambda: True)),
                  mock.patch("builtins.input", return_value=hashlib.sha256(self.candidate).hexdigest()),
                  mock.patch.object(signer.getpass, "getpass", return_value=_PASSWORD.decode()),
                  mock.patch.object(signer.sys, "stdout", io.StringIO()),
                  mock.patch.object(signer.sys, "stderr", io.StringIO())):
                self.assertEqual(signer.main(), 0)
                original = output.read_bytes()
                self.assertEqual(signer.main(), 1)
                self.assertEqual(output.read_bytes(), original)
            SignedPromptAdmission(
                public_key=self.public, signed_manifest=original,
                expected_manifest_sha256=hashlib.sha256(original).digest(),
            )

    def test_interactive_cli_wrong_confirmation_leaves_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, private, output = (base / "candidate.json", base / "private.pem",
                                       base / "admission.json")
            source.write_bytes(self.candidate)
            private.write_bytes(self.pem)
            args = ["prompt_admission_sign.py", "sign", str(source), str(private),
                    str(output), "developer.synthetic", "1"]
            with (mock.patch.object(signer.sys, "argv", args),
                  mock.patch.object(signer.sys, "stdin", mock.Mock(isatty=lambda: True)),
                  mock.patch("builtins.input", return_value="wrong"),
                  mock.patch.object(signer.getpass, "getpass", return_value=_PASSWORD.decode()),
                  mock.patch.object(signer.sys, "stdout", io.StringIO()),
                  mock.patch.object(signer.sys, "stderr", io.StringIO())):
                self.assertEqual(signer.main(), 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
