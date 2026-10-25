from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smoke_packaged_platform_write_https import (  # noqa: E402
    KEY_REFS, current_packaged_api_restart, current_packaged_postgres_restart, smoke,
)
from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE  # noqa: E402


class PackagedPlatformWriteSmokeTests(unittest.TestCase):
    def test_api_restart_hook_is_unavailable_outside_owned_smoke_callback(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "only inside its smoke callback"):
            current_packaged_api_restart()

    def test_postgres_restart_hook_is_unavailable_outside_owned_smoke_callback(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "only inside its smoke callback"):
            current_packaged_postgres_restart()

    def test_licensed_probe_requires_paired_document_factory(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with self.assertRaisesRegex(ValueError, "must be paired"):
            smoke(*paths, licensed_https_probe=lambda **_kwargs: None)

    def test_malformed_synthetic_document_rejected_before_layout_copy(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with patch("smoke_packaged_platform_write_https.credential_exists", return_value=False):
            with patch("smoke_packaged_platform_write_https.windows_local_macs",
                       return_value=frozenset({"00:11:22:33:44:55"})):
                with patch("smoke_packaged_platform_write_https.rehearse") as placement:
                    with self.assertRaisesRegex(ValueError, "signed document rejected"):
                        smoke(*paths, layout_verifier=lambda *_args: {"file_count": 1},
                              synthetic_license_document_factory=lambda *_args: b"",
                              licensed_https_probe=lambda **_kwargs: None)
                    placement.assert_not_called()

    def test_synthetic_public_key_uses_actual_embedded_packages_root(self) -> None:
        self.assertEqual(PUBLIC_KEY_RELATIVE,
                         "runtime/python/packages/plm_assistant/modules/license/trust/product_public_key.json")
        self.assertEqual(len(KEY_REFS), len(set(KEY_REFS)))

    def test_synthetic_vault_fixture_covers_current_cursor_key_refs(self) -> None:
        entrypoints = (Path(__file__).resolve().parents[2] / "apps" / "backend" /
                       "src" / "plm_assistant" / "entrypoints")
        refs: set[str] = set()
        for path in entrypoints.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                        node.value, ast.Constant) and isinstance(node.value.value, str):
                    if node.value.value.endswith(("-cursor-v1", "-token-v1")):
                        refs.add(node.value.value)
        self.assertTrue(refs <= set(KEY_REFS))

    def test_existing_fixed_vault_target_rejects_before_copy(self) -> None:
        paths = tuple(Path(name) for name in ("candidate", "source", "stage", "pristine", "target"))
        with patch("smoke_packaged_platform_write_https.verify_layout",
                   return_value={"file_count": 21115, "mapping_sha256": "fixed"}):
            with patch("smoke_packaged_platform_write_https.credential_exists", return_value=True):
                with patch("smoke_packaged_platform_write_https.rehearse") as placement:
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        smoke(*paths)
                    placement.assert_not_called()


if __name__ == "__main__":
    unittest.main()
