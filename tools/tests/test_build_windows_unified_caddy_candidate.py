from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_caddy_candidate import EXTRA_COUNT, TEMPLATE_NAME, _extra_inputs, build


class BuildCaddyCandidateTests(unittest.TestCase):
    def test_extra_input_names_and_pinned_template(self) -> None:
        template = Path(__file__).resolve().parents[2] / "deploy/windows/Caddyfile.template"
        text = template.read_text(encoding="ascii")
        self.assertIn("__PUBLIC_HOST__", text)
        self.assertIn('respond "Misdirected Request" 421', text)
        self.assertEqual(EXTRA_COUNT, 7)
        self.assertEqual(TEMPLATE_NAME, "payload/config/Caddyfile.template")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "template"):
                _extra_inputs(Path(directory), Path(directory) / "wrong-template")

    def test_missing_output_parent_fails_before_source_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "output parent"):
                build(root / "missing.zip", root, root / "missing-template",
                      root / "missing-output")


if __name__ == "__main__":
    unittest.main()
