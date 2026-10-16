from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_paddle_model_revisions import audit


def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class PinnedModelAuditTests(unittest.TestCase):
    def test_exact_objects_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            models = {}
            dirs = {}
            for role in ("det", "rec"):
                directory = Path(temp) / role
                directory.mkdir()
                dirs[role] = directory
                rev = role * 40
                objects = {}
                for name in ("config.json", "inference.json", "inference.pdiparams", "inference.yml", "README.md"):
                    data = b"---\nlicense: apache-2.0\n---\n" if name == "README.md" else (role + name).encode()
                    (directory / name).write_bytes(data)
                    objects[name] = hashlib.sha256(data).hexdigest() if name == "inference.pdiparams" else blob(data)
                    if name != "README.md":
                        metadata = directory / ".cache" / "huggingface" / "download"
                        metadata.mkdir(parents=True, exist_ok=True)
                        (metadata / f"{name}.metadata").write_text(f"{rev}\n{objects[name]}\n", encoding="utf-8")
                models[role] = {"revision": rev, "objects": objects}
            with patch("audit_paddle_model_revisions.MODELS", models):
                result = audit(dirs["det"], dirs["rec"])
                self.assertEqual(result["status"], "PINNED_MODEL_BYTES_PASS")
                self.assertFalse(result["release_eligible"])
                metadata = dirs["det"] / ".cache" / "huggingface" / "download" / "config.json.metadata"
                metadata.write_text("wrong-revision\n" + models["det"]["objects"]["config.json"] + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "cache revision mismatch"):
                    audit(dirs["det"], dirs["rec"])
                metadata.write_text(models["det"]["revision"] + "\n" + models["det"]["objects"]["config.json"] + "\n", encoding="utf-8")
                (dirs["rec"] / "inference.json").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "object mismatch"):
                    audit(dirs["det"], dirs["rec"])


if __name__ == "__main__":
    unittest.main()
