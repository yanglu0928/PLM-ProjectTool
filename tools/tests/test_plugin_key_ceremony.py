from __future__ import annotations

import base64
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


_TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "developer-workbench"
    / "plugin_key_ceremony.py"
)
_SPEC = importlib.util.spec_from_file_location("plugin_key_ceremony_under_test", _TOOL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("unable to load developer workbench ceremony")
_TOOL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TOOL)


def _hosted_temp() -> tempfile.TemporaryDirectory[str]:
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp or Path(runner_temp).drive.upper() != "D:":
        raise RuntimeError("key ceremony tests require GitHub hosted D-drive runner temp")
    return tempfile.TemporaryDirectory(dir=runner_temp)


class PluginKeyCeremonyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = _hosted_temp()
        root = Path(self.temp.name)
        self.private = root / "private" / "plugin-signing-v1.pem"
        self.public = root / "package" / "developer_keys.json"
        self.private.parent.mkdir()
        self.public.parent.mkdir()
        self.public.write_text(
            json.dumps({
                "schema_version": "plm.plugin.publisher-keys.v1",
                "keys": [],
            }),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_and_verify_synthetic_pair_and_passphrase_wipe(self) -> None:
        password = bytearray(b"synthetic-only-long-passphrase")
        _TOOL.create_pair(self.private, self.public, password)
        self.assertEqual(password, bytearray(len(password)))
        self.assertTrue(self.private.is_file())
        manifest = json.loads(self.public.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "plm.plugin.publisher-keys.v1")
        self.assertEqual(len(manifest["keys"]), 1)
        self.assertEqual(manifest["keys"][0]["algorithm"], "Ed25519")
        self.assertEqual(manifest["keys"][0]["state"], "ACTIVE")
        self.assertEqual(len(base64.b64decode(manifest["keys"][0]["public_key"])), 32)

        offline = self.private.parent / "offline-copy.pem"
        offline.write_bytes(self.private.read_bytes())
        _TOOL.verify_pair(
            offline,
            self.public,
            bytearray(b"synthetic-only-long-passphrase"),
            signer_key_ref="plm-plugin-publisher-v1",
        )

    def test_existing_private_or_nonempty_manifest_never_gets_overwritten(self) -> None:
        _TOOL.create_pair(
            self.private,
            self.public,
            bytearray(b"synthetic-only-long-passphrase"),
        )
        before_private = self.private.read_bytes()
        before_public = self.public.read_bytes()
        with self.assertRaises(_TOOL.PluginKeyCeremonyError):
            _TOOL.create_pair(
                self.private,
                self.public,
                bytearray(b"another-synthetic-passphrase"),
            )
        self.assertEqual(self.private.read_bytes(), before_private)
        self.assertEqual(self.public.read_bytes(), before_public)

    def test_wrong_password_and_mismatched_pair_fail_without_material(self) -> None:
        _TOOL.create_pair(
            self.private,
            self.public,
            bytearray(b"synthetic-only-long-passphrase"),
        )
        with self.assertRaises(_TOOL.PluginKeyCeremonyError):
            _TOOL.verify_pair(
                self.private,
                self.public,
                bytearray(b"wrong-synthetic-passphrase"),
            )

        other = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        manifest = json.loads(self.public.read_text(encoding="utf-8"))
        manifest["keys"][0]["public_key"] = base64.b64encode(other).decode("ascii")
        self.public.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(_TOOL.PluginKeyCeremonyError):
            _TOOL.verify_pair(
                self.private,
                self.public,
                bytearray(b"synthetic-only-long-passphrase"),
            )

    def test_invalid_manifest_key_and_path_shapes_are_rejected(self) -> None:
        self.public.write_text('{"schema_version":"wrong","keys":[]}', encoding="utf-8")
        with self.assertRaises(_TOOL.PluginKeyCeremonyError):
            _TOOL.create_pair(
                self.private,
                self.public,
                bytearray(b"synthetic-only-long-passphrase"),
            )
        with self.assertRaises(_TOOL.PluginKeyCeremonyError):
            _TOOL.create_pair(
                Path("relative.pem"),
                self.public,
                bytearray(b"synthetic-only-long-passphrase"),
            )


if __name__ == "__main__":
    unittest.main()
